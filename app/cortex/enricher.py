import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

BATCH_SIZE = 30

SYSTEM_PROMPT = """\
You are a job analyst. Given a list of job offers, detect the required seniority level for each.

Rules:
- "junior"  : entry-level, 0-3 years, first job, graduate, no prior experience required
- "mid"     : 3-7 years, confirmed, intermediate
- "senior"  : 7+ years, lead, architect, expert, principal
- ""        : unclear or not mentioned

Process ALL jobs. Return the same index as the input.
"""


class _JobSeniority(BaseModel):
    index: int = Field(description="0-based index from the input list")
    seniority: str = Field(description='junior | mid | senior | ""')


class _EnrichOutput(BaseModel):
    jobs: list[_JobSeniority]


async def _enrich_batch(llm, batch: list[dict], batch_idx: int) -> list[dict]:
    jobs_text = "\n\n".join(
        f"[{i}] {j['title']} @ {j['company']}\n{j.get('desc', '')[:300]}"
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
        return enriched
    except Exception as exc:
        logger.warning("[enricher] Batch %d failed: %s — storing without seniority", batch_idx, exc)
        return batch


async def enrich_seniority(jobs: list[dict]) -> list[dict]:
    if not jobs:
        return []

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(_EnrichOutput)

    batches = [jobs[i:i + BATCH_SIZE] for i in range(0, len(jobs), BATCH_SIZE)]
    logger.info("[enricher] %d jobs → %d batches for seniority detection", len(jobs), len(batches))

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