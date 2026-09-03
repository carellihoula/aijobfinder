import numpy as np
from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.cv.vectorize import (
    KEYWORD_SKILLS_WEIGHT,
    VECTOR_WEIGHTS,
    build_cv_vector_texts,
    flatten_vector_texts,
    keyword_overlap_score,
    regroup_vectors,
)
from app.logger import get_logger
from app.observability.langfuse_client import count_tokens, traced_embedding
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

MAX_JOBS = 60  # llm_reranker caps its own input at the same count - no point keeping more


def _fused_similarity(
    cv_vectors: dict,
    job_skills_vectors: np.ndarray,
    job_context_vectors: np.ndarray,
) -> np.ndarray:
    """Weighted fusion of per-facet cosine similarities against each job's two
    vectors (skills, context) - every CV facet is compared against BOTH and
    the better match wins, mirroring cortex_svc.search_jobs' SQL fusion
    exactly (same weights, same pooling: LEAST() over distances there, MAX()
    over similarities here, since similarity is just distance's complement)."""
    present_weights = {k: VECTOR_WEIGHTS[k] for k in cv_vectors if k in VECTOR_WEIGHTS}
    total_weight = sum(present_weights.values())

    fused = np.zeros(job_skills_vectors.shape[0])
    for name, weight in present_weights.items():
        normalized_weight = weight / total_weight
        vectors = cv_vectors["experiences"] if name == "experiences" else [cv_vectors[name]]
        facet_matrix = np.array(vectors)
        sim_skills = cosine_similarity(facet_matrix, job_skills_vectors).max(axis=0)
        sim_context = cosine_similarity(facet_matrix, job_context_vectors).max(axis=0)
        facet_sim = np.maximum(sim_skills, sim_context)  # best of the two job vectors
        fused += normalized_weight * facet_sim
    return fused


async def embeddings_filter_node(state: PipelineState) -> dict:
    """Node 5 - Semantic filter: keep the top MAX_JOBS by fused similarity with CV."""
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

    # Same two-vector split as the offer side at ingestion (title+skills vs
    # raw description) - job.get("skills") is only populated for jobs sourced
    # from the Cortex (LLM-extracted at ingestion); jobs from the JSearch/
    # Adzuna fallback path simply have none, degrading gracefully to title-only.
    job_skills_texts = [
        (f"{job.get('title', '')} " + ", ".join(job.get("skills") or [])).strip()
        for job in jobs
    ]
    job_context_texts = [job.get("desc", "") or "" for job in jobs]

    logger.info(
        "[embeddings_filter] Embedding CV (%d facet vectors) + %d jobs x2 (model=%s) ...",
        len(cv_flat_texts), len(jobs), settings.OPENAI_EMBEDDING_MODEL,
    )

    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )

    # Single batch call: every CV facet vector, then every job's skills text,
    # then every job's context text
    n_cv = len(cv_flat_texts)
    n_jobs = len(jobs)
    all_texts = cv_flat_texts + job_skills_texts + job_context_texts
    with traced_embedding("embeddings_filter.embed_cv_and_jobs", settings.OPENAI_EMBEDDING_MODEL) as span:
        all_vectors = await embedder.aembed_documents(all_texts)
        span.update(usage_details={"input": count_tokens(all_texts, settings.OPENAI_EMBEDDING_MODEL)})
    cv_vectors = regroup_vectors(cv_flat_keys, all_vectors[:n_cv])
    job_skills_vectors = np.array(all_vectors[n_cv:n_cv + n_jobs])
    job_context_vectors = np.array(all_vectors[n_cv + n_jobs:])

    scores = _fused_similarity(cv_vectors, job_skills_vectors, job_context_vectors)

    # Exact skill-keyword overlap bonus, on top of the fused embedding score -
    # see keyword_overlap_score() for why this isn't just folded into the
    # weighted budget above.
    cv_skills = cv.get("skills") or []
    keyword_bonuses = np.array([
        keyword_overlap_score(cv_skills, job.get("skills") or [])
        for job in jobs
    ])
    scores = scores + KEYWORD_SKILLS_WEIGHT * keyword_bonuses

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