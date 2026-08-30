import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

BATCH_SIZE = 30
DESC_CHARS_FOR_ENRICHMENT = 1500  # enough to reach a "profil recherché" section further down

SYSTEM_PROMPT = """\
You are a job analyst. Given a list of job offers, for each one detect the \
required seniority level AND extract the key skills required.

Seniority rules:
- "junior"  : entry-level, 0-3 years, first job, graduate, no prior experience required
- "mid"     : 3-7 years, confirmed, intermediate
- "senior"  : 7+ years, lead, architect, expert, principal
- ""        : unclear or not mentioned

Skills rules:
- Extract concrete technical/professional skills required by the posting
  (languages, frameworks, tools, methodologies, certifications).
- Be concise: short skill names, not full sentences (e.g. "Python", not
  "experience writing Python code").
- Empty list if none are clearly stated.

Process ALL jobs. Return the same index as the input.
"""


class _JobEnrichment(BaseModel):
    index: int = Field(description="0-based index from the input list")
    seniority: str = Field(description='junior | mid | senior | ""')
    skills: list[str] = Field(default_factory=list, description="Key skills required by this job")


class _EnrichOutput(BaseModel):
    jobs: list[_JobEnrichment]


def _build_llms():
    """Primary LLM is Gemini Flash-Lite (free tier) when configured - this task
    (seniority + skills extraction on public job postings) is high-volume and
    low-stakes. Falls back to OPENAI_MODEL_LIGHT per-batch on any Gemini
    failure (quota, auth, malformed output, ...), or straight to it when no
    Gemini key is set - a simple extraction task, no need for a bigger model."""
    openai_llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_LIGHT,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(_EnrichOutput)

    gemini_llm = None
    if settings.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI
        gemini_llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY,
        ).with_structured_output(_EnrichOutput)

    return gemini_llm, openai_llm


async def _enrich_batch(gemini_llm, openai_llm, batch: list[dict], batch_idx: int) -> list[dict]:
    jobs_text = "\n\n".join(
        f"[{i}] {j['title']} @ {j['company']}\n{j.get('desc', '')[:DESC_CHARS_FOR_ENRICHMENT]}"
        for i, j in enumerate(batch)
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=jobs_text),
    ]

    result: _EnrichOutput | None = None
    if gemini_llm is not None:
        try:
            result = await gemini_llm.ainvoke(messages)
        except Exception as exc:
            logger.warning("[enricher] Batch %d - Gemini failed (%s), falling back to OpenAI", batch_idx, exc)

    if result is None:
        try:
            result = await openai_llm.ainvoke(messages)
        except Exception as exc:
            logger.warning("[enricher] Batch %d failed on both providers: %s - storing without enrichment", batch_idx, exc)
            return batch

    enriched = [dict(j) for j in batch]
    for meta in result.jobs:
        if meta.index < len(enriched):
            enriched[meta.index]["seniority"] = meta.seniority
            enriched[meta.index]["skills"] = meta.skills
    return enriched


async def enrich_jobs(jobs: list[dict]) -> list[dict]:
    """Tag each job with seniority and extract its required skills, in one
    batched LLM pass per provider - both pieces of info come from reading the
    same posting, no point paying for two separate calls."""
    if not jobs:
        return []

    gemini_llm, openai_llm = _build_llms()

    batches = [jobs[i:i + BATCH_SIZE] for i in range(0, len(jobs), BATCH_SIZE)]
    logger.info(
        "[enricher] %d jobs → %d batches for seniority + skills extraction (primary=%s)",
        len(jobs), len(batches), "gemini" if gemini_llm else "openai",
    )

    results = await asyncio.gather(
        *[_enrich_batch(gemini_llm, openai_llm, batch, i) for i, batch in enumerate(batches)],
        return_exceptions=True,
    )

    enriched: list[dict] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning("[enricher] Batch %d exception: %s", i, r)
            enriched.extend(batches[i])
        else:
            enriched.extend(r)

    return enriched
