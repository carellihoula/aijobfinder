import numpy as np
from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.cv.vectorize import (
    VECTOR_WEIGHTS,
    build_cv_vector_texts,
    flatten_vector_texts,
    regroup_vectors,
)
from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

MAX_JOBS = 60  # llm_reranker caps its own input at the same count - no point keeping more


def _fused_similarity(cv_vectors: dict, job_vectors: np.ndarray) -> np.ndarray:
    """Weighted fusion of per-facet cosine similarities against each job
    vector. Mirrors cortex_svc.search_jobs' SQL fusion exactly (same weights,
    same pooling) - there it's a weighted sum of distances with LEAST() over
    experiences, here it's a weighted sum of similarities with MAX() over
    experiences, since similarity is just distance's complement."""
    present_weights = {k: VECTOR_WEIGHTS[k] for k in cv_vectors if k in VECTOR_WEIGHTS}
    total_weight = sum(present_weights.values())

    fused = np.zeros(job_vectors.shape[0])
    for name, weight in present_weights.items():
        normalized_weight = weight / total_weight
        if name == "experiences":
            exp_matrix = np.array(cv_vectors["experiences"])
            sims = cosine_similarity(exp_matrix, job_vectors)
            facet_sim = sims.max(axis=0)  # best-matching experience per job
        else:
            vec = np.array(cv_vectors[name]).reshape(1, -1)
            facet_sim = cosine_similarity(vec, job_vectors)[0]
        fused += normalized_weight * facet_sim
    return fused


async def embeddings_filter_node(state: PipelineState) -> dict:
    """Node 5 - Semantic filter: keep jobs above mean fused similarity with CV."""
    cv = state.get("cv_json") or {}
    jobs = state.get("jobs") or []

    if not jobs:
        logger.warning("[embeddings_filter] No jobs to filter")
        return {"filtered_jobs": []}

    cv_vector_texts = build_cv_vector_texts(cv)
    if not cv_vector_texts:
        logger.warning("[embeddings_filter] Empty CV profile - keeping all jobs unfiltered")
        return {"filtered_jobs": jobs}

    cv_flat_texts, cv_flat_keys = flatten_vector_texts(cv_vector_texts)
    job_texts = [
        f"{job.get('title', '')} {job.get('desc', '')}".strip()
        for job in jobs
    ]

    logger.info(
        "[embeddings_filter] Embedding CV (%d facet vectors) + %d jobs (model=%s) ...",
        len(cv_flat_texts), len(jobs), settings.OPENAI_EMBEDDING_MODEL,
    )

    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )

    # Single batch call: every CV facet vector first, then all jobs
    all_vectors = await embedder.aembed_documents(cv_flat_texts + job_texts)
    cv_vectors = regroup_vectors(cv_flat_keys, all_vectors[:len(cv_flat_texts)])
    job_vectors = np.array(all_vectors[len(cv_flat_texts):])

    scores = _fused_similarity(cv_vectors, job_vectors)

    scored_jobs = sorted(
        [{**job, "_score": round(float(score), 4)} for job, score in zip(jobs, scores)],
        key=lambda j: j["_score"],
        reverse=True,
    )

    # Fixed top-K instead of "above the batch's mean score" - a mean cutoff
    # always rejects roughly half the lot regardless of absolute quality: a
    # strong job in an exceptional batch could get cut, a weak job in a poor
    # batch could pass. A fixed count doesn't depend on today's distribution.
    filtered = scored_jobs[:MAX_JOBS]

    logger.info(
        "[embeddings_filter] %d jobs in → %d kept (best=%.4f, worst kept=%.4f)",
        len(jobs), len(filtered),
        scored_jobs[0]["_score"],
        filtered[-1]["_score"],
    )
    return {"filtered_jobs": filtered}