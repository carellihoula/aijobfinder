import numpy as np
from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

MIN_JOBS = 5  # always keep at least this many jobs for the reranker


def _build_cv_text(cv: dict) -> str:
    parts = []
    if cv.get("roles"):
        parts.append("Roles: " + ", ".join(cv["roles"]))
    if cv.get("skills"):
        parts.append("Skills: " + ", ".join(cv["skills"][:20]))
    if cv.get("summary"):
        parts.append(cv["summary"])
    if cv.get("level"):
        parts.append("Level: " + cv["level"])
    return " | ".join(parts)


async def embeddings_filter_node(state: PipelineState) -> dict:
    """Node 5 - Semantic filter: keep jobs above mean cosine similarity with CV."""
    cv = state.get("cv_json") or {}
    jobs = state.get("jobs") or []

    if not jobs:
        logger.warning("[embeddings_filter] No jobs to filter")
        return {"filtered_jobs": []}

    cv_text = _build_cv_text(cv)
    job_texts = [
        f"{job.get('title', '')} {job.get('desc', '')}".strip()
        for job in jobs
    ]

    logger.info(
        "[embeddings_filter] Embedding CV + %d jobs (model=%s) ...",
        len(jobs), settings.OPENAI_EMBEDDING_MODEL,
    )

    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )

    # Single batch call: CV first, then all jobs
    all_vectors = await embedder.aembed_documents([cv_text] + job_texts)
    cv_vector = np.array(all_vectors[0]).reshape(1, -1)
    job_vectors = np.array(all_vectors[1:])

    scores = cosine_similarity(cv_vector, job_vectors)[0]

    scored_jobs = sorted(
        [{**job, "_score": round(float(score), 4)} for job, score in zip(jobs, scores)],
        key=lambda j: j["_score"],
        reverse=True,
    )

    mean_score = float(np.mean(scores))
    filtered = [j for j in scored_jobs if j["_score"] >= mean_score]

    # Guarantee minimum jobs for the reranker
    if len(filtered) < MIN_JOBS:
        filtered = scored_jobs[:MIN_JOBS]

    logger.info(
        "[embeddings_filter] %d jobs in → %d kept (mean=%.4f, best=%.4f, worst kept=%.4f)",
        len(jobs), len(filtered), mean_score,
        scored_jobs[0]["_score"],
        filtered[-1]["_score"],
    )
    return {"filtered_jobs": filtered}