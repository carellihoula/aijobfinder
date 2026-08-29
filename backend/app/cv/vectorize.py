"""Shared CV multi-vector logic.

Split into its own module so the two places that need it - the Cortex ANN
search (`pipeline/nodes/cortex_search.py`, fused in SQL via pgvector) and the
post-search semantic filter (`pipeline/nodes/embeddings_filter.py`, fused in
Python via sklearn) - use the exact same text segmentation and the exact same
facet weights. Keeping this in two independent copies would let them drift
apart silently.
"""

MAX_EXPERIENCE_VECTORS = 5

# Base weight of each CV vector in the fused match score. Renormalized at query
# time over whichever vectors are actually present (e.g. a CV with no summary
# redistributes its weight across the others instead of being penalized for it).
VECTOR_WEIGHTS = {
    "competences": 0.35,
    "summary": 0.12,
    "experiences": 0.35,
    "formations": 0.18,
}


def build_cv_vector_texts(cv: dict) -> dict:
    """
    Split the CV profile into the separate text segments to embed for fused
    matching - one vector per facet instead of one blob, so a verbose summary
    can't drown out skills, and one strong past experience isn't averaged away
    by unrelated ones.

    Level/experience_years are deliberately left out - seniority isn't reliable
    to compare by cosine similarity (same reason job seniority is a hard
    filter, LLM-tagged at ingestion, rather than embedded). Names, emails,
    phones, addresses, and dates never make it into cv_json's semantic fields
    in the first place.

    Missing sections are simply omitted from the result - callers redistribute
    their weight across whichever vectors are present.
    """
    result: dict = {}

    competences_parts = []
    if cv.get("roles"):
        competences_parts.append("Roles: " + ", ".join(cv["roles"]))
    if cv.get("skills"):
        competences_parts.append("Skills: " + ", ".join(cv["skills"][:20]))
    if competences_parts:
        result["competences"] = " | ".join(competences_parts)

    if cv.get("summary"):
        result["summary"] = cv["summary"]

    exp_texts = []
    for exp in cv.get("experiences", []):
        desc = (exp.get("description") or "").strip()
        if not desc:
            continue
        title = (exp.get("title") or "").strip()
        exp_texts.append(f"{title}: {desc}" if title else desc)
    if exp_texts:
        # CVs are conventionally listed most-recent-first; not guaranteed, but
        # the closest signal we have without parsing free-text dates.
        result["experiences"] = exp_texts[:MAX_EXPERIENCE_VECTORS]

    degrees = [e.get("degree") for e in cv.get("education", []) if e.get("degree")]
    if degrees:
        result["formations"] = ", ".join(degrees)

    return result


def flatten_vector_texts(vector_texts: dict) -> tuple[list[str], list[tuple[str, int | None]]]:
    """Flatten {name: text | list[text]} into a parallel (texts, keys) pair so
    every CV facet - however many "experiences" entries there are - can be
    embedded in a single batched API call."""
    flat_texts: list[str] = []
    flat_keys: list[tuple[str, int | None]] = []
    for name, value in vector_texts.items():
        if name == "experiences":
            for i, text_ in enumerate(value):
                flat_texts.append(text_)
                flat_keys.append((name, i))
        else:
            flat_texts.append(value)
            flat_keys.append((name, None))
    return flat_texts, flat_keys


def regroup_vectors(flat_keys: list[tuple[str, int | None]], raw_vectors: list) -> dict:
    """Inverse of `flatten_vector_texts`: regroup embedded vectors back into
    {name: vector | list[vector]}."""
    query_vectors: dict = {}
    for (name, idx), vec in zip(flat_keys, raw_vectors):
        if idx is None:
            query_vectors[name] = vec
        else:
            query_vectors.setdefault(name, []).append(vec)
    return query_vectors
