import asyncio

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.logger import get_logger
from app.observability.langfuse_client import get_langfuse_callbacks
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

BATCH_SIZE = 30   # jobs per LLM call
MAX_BATCHES = 2   # max 60 jobs total
MIN_SCORE = 5
MIN_MATCHES = 3


class _JobMatch(BaseModel):
    index: int = Field(description="0-based index of the job in the input list")
    score: int = Field(description="Match score from 0 to 10", ge=0, le=10)
    matching_skills: list[str] = Field(description="Skills from the CV that match this job's requirements")
    missing_skills: list[str] = Field(description="Skills required by the job but absent from the CV")
    reason: str = Field(description="1-2 sentences explaining the match quality")


class _RerankerOutput(BaseModel):
    matches: list[_JobMatch]


_SYSTEM_PROMPT_BASE = """\
You are an expert technical recruiter.
Given a candidate profile and a list of job offers, evaluate each job's compatibility with the candidate.

For EACH job in the list, provide:
- A score from 0 to 10 (10 = perfect match, 0 = completely irrelevant)
- Skills from the candidate's profile that match the job requirements
- Skills required by the job but missing from the candidate
- A concise 1-2 sentence explanation of the match quality

Scoring guide:
  9-10 : All key requirements met, strong skills alignment, right seniority level
  7-8  : Most requirements met, minor gaps
  5-6  : Partial match, notable missing skills or seniority mismatch
  3-4  : Weak match, significant gaps
  0-2  : Irrelevant or completely mismatched domain

Be rigorous: penalize mismatches in seniority, domain, or critical missing skills.
You MUST evaluate ALL jobs provided.
"""

_EXPERIENCE_LABELS = {
    "junior": "junior (0–3 years of experience)",
    "mid": "mid-level (3–7 years of experience)",
    "senior": "senior (7+ years of experience)",
}


def _build_system_prompt(experience_level: str) -> str:
    if not experience_level or experience_level not in _EXPERIENCE_LABELS:
        return _SYSTEM_PROMPT_BASE
    label = _EXPERIENCE_LABELS[experience_level]
    return (
        _SYSTEM_PROMPT_BASE
        + f"\nIMPORTANT: The candidate is targeting {label} positions. "
        "Significantly penalize jobs that clearly target a different seniority level.\n"
    )


def _format_cv(cv: dict) -> str:
    lines = [
        f"Level: {cv.get('level', 'unknown')} | "
        f"Experience: {cv.get('experience_years', 0)} years",
    ]
    if cv.get("roles"):
        lines.append(f"Target roles: {', '.join(cv['roles'])}")
    if cv.get("skills"):
        lines.append(f"Skills: {', '.join(cv['skills'])}")
    if cv.get("experiences"):
        lines.append("Work experience:")
        for exp in cv["experiences"][:5]:
            date_range = f"{exp.get('start_date', '')} - {exp.get('end_date', 'present')}"
            lines.append(f"  • {exp.get('title', '')} @ {exp.get('company', '')} ({date_range})")
            if exp.get("description"):
                lines.append(f"    {exp['description'][:200]}")
    if cv.get("education"):
        lines.append("Education:")
        for edu in cv["education"][:3]:
            lines.append(f"  • {edu.get('degree', '')} - {edu.get('school', '')}")
    if cv.get("languages"):
        langs = [f"{l['name']} ({l.get('level', '')})" for l in cv["languages"]]
        lines.append(f"Languages: {', '.join(langs)}")
    return "\n".join(lines)


def _format_jobs(jobs: list[dict]) -> str:
    lines = []
    for i, job in enumerate(jobs):
        lines.append(
            f"\n[{i}] {job.get('title', 'N/A')} @ {job.get('company', 'N/A')} "
            f"- {job.get('location', 'N/A')}"
        )
        lines.append(f"    {job.get('desc', '')[:400]}")
    return "\n".join(lines)


async def _rank_batch(structured_llm, cv_text: str, batch: list[dict], batch_index: int, system_prompt: str) -> list[dict]:
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"## Candidate profile\n{cv_text}\n\n"
            f"## Job offers to evaluate\n{_format_jobs(batch)}"
        )),
    ]
    result: _RerankerOutput = await structured_llm.ainvoke(messages)
    return [
        {
            "job": batch[m.index],
            "score": m.score,
            "matching_skills": m.matching_skills,
            "missing_skills": m.missing_skills,
            "reason": m.reason,
        }
        for m in result.matches
        if m.index < len(batch)
    ]


async def llm_reranker_node(state: PipelineState) -> dict:
    """Node 6 - Batch LLM reranker: 2 parallel batches of 30 = 60 jobs max."""
    cv = state.get("cv_json") or {}
    filtered_jobs = state.get("filtered_jobs") or []
    experience_level: str = state.get("experience_level") or ""

    if not filtered_jobs:
        logger.warning("[llm_reranker] No filtered jobs to rerank")
        return {"matches": []}

    # Cap at MAX_BATCHES × BATCH_SIZE - embedding filter is responsible for the rest
    jobs_to_rank = filtered_jobs[:BATCH_SIZE * MAX_BATCHES]
    batches = [
        jobs_to_rank[i:i + BATCH_SIZE]
        for i in range(0, len(jobs_to_rank), BATCH_SIZE)
    ]

    logger.info(
        "[llm_reranker] %d jobs → %d batch(es) of %d (parallel)",
        len(jobs_to_rank), len(batches), BATCH_SIZE,
    )

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_LIGHT,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
        callbacks=get_langfuse_callbacks(),
    )
    structured_llm = llm.with_structured_output(_RerankerOutput)
    cv_text = _format_cv(cv)
    system_prompt = _build_system_prompt(experience_level)

    results = await asyncio.gather(
        *[_rank_batch(structured_llm, cv_text, batch, i, system_prompt) for i, batch in enumerate(batches)],
        return_exceptions=True,
    )

    all_matches: list[dict] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning("[llm_reranker] Batch %d failed: %s", i, result)
            continue
        all_matches.extend(result)

    all_matches.sort(key=lambda m: m["score"], reverse=True)

    above = [m for m in all_matches if m["score"] >= MIN_SCORE]
    final_matches = above if len(above) >= MIN_MATCHES else all_matches[:MIN_MATCHES]

    logger.info(
        "[llm_reranker] %d jobs evaluated → %d matches kept (best=%d, worst=%d)",
        len(jobs_to_rank), len(final_matches),
        final_matches[0]["score"] if final_matches else 0,
        final_matches[-1]["score"] if final_matches else 0,
    )
    return {"matches": final_matches}