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


async def _enrich_batch(llm, batch: list[dict], batch_idx: int) -> list[dict]:
    jobs_text = "\n\n".join(
        f"[{i}] {j['title']} @ {j['company']}\n{j.get('desc', '')[:DESC_CHARS_FOR_ENRICHMENT]}"
        for i, j in enumerate(batch)
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=jobs_text),
    ]
    try:
        result: _EnrichOutput = await llm.ainvoke(messages)
        enriched = [dict(j) for j in batch]
        for meta in result.jobs:
            if meta.index < len(enriched):
                enriched[meta.index]["seniority"] = meta.seniority
                enriched[meta.index]["skills"] = meta.skills
        return enriched
    except Exception as exc:
        logger.warning("[enricher] Batch %d failed: %s - storing without enrichment", batch_idx, exc)
        return batch


async def enrich_jobs(jobs: list[dict]) -> list[dict]:
    """Tag each job with seniority and extract its required skills, in one
    batched LLM pass - both pieces of info come from reading the same posting,
    no point paying for two separate calls."""
    if not jobs:
        return []

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(_EnrichOutput)

    batches = [jobs[i:i + BATCH_SIZE] for i in range(0, len(jobs), BATCH_SIZE)]
    logger.info("[enricher] %d jobs → %d batches for seniority + skills extraction", len(jobs), len(batches))

    results = await asyncio.gather(
        *[_enrich_batch(llm, batch, i) for i, batch in enumerate(batches)],
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