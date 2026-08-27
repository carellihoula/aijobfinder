import asyncio
import time

import httpx

from app.config import settings
from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

_ADZUNA_SEM = asyncio.Semaphore(4)

_MOCK_JOBS = [
    {"title": "Senior Python Developer", "company": "TechCorp", "location": "Paris", "desc": "5+ years Python, FastAPI, PostgreSQL, Docker, AWS, REST APIs, microservices.", "url": "", "date": ""},
    {"title": "ML Engineer", "company": "AI Labs", "location": "Remote", "desc": "Python, TensorFlow, PyTorch, scikit-learn, MLflow, model deployment, data pipelines.", "url": "", "date": ""},
    {"title": "Data Scientist", "company": "DataCo", "location": "Lyon", "desc": "Python, SQL, pandas, numpy, scikit-learn, statistical analysis, A/B testing.", "url": "", "date": ""},
    {"title": "AI/LLM Engineer", "company": "StartupAI", "location": "Remote", "desc": "Python, LangChain, LangGraph, OpenAI API, prompt engineering, RAG, vector databases.", "url": "", "date": ""},
    {"title": "Backend Engineer", "company": "ScaleUp", "location": "Paris", "desc": "Python, FastAPI, Node.js, PostgreSQL, Redis, Docker, microservices, REST APIs.", "url": "", "date": ""},
    {"title": "Full Stack Developer", "company": "WebAgency", "location": "Bordeaux", "desc": "React, TypeScript, Python, Django, PostgreSQL, Docker, CI/CD.", "url": "", "date": ""},
    {"title": "Data Engineer", "company": "BigData Inc", "location": "Remote", "desc": "Python, Apache Spark, Airflow, dbt, Snowflake, SQL, ETL/ELT, Kafka.", "url": "", "date": ""},
    {"title": "DevOps Engineer", "company": "CloudFirst", "location": "Paris", "desc": "Docker, Kubernetes, AWS, Terraform, CI/CD, Linux, Python scripting.", "url": "", "date": ""},
    {"title": "NLP Engineer", "company": "TextAI", "location": "Remote", "desc": "Python, spaCy, transformers, BERT, GPT, text classification, NER.", "url": "", "date": ""},
    {"title": "Cloud Architect", "company": "CloudSys", "location": "Paris", "desc": "AWS, microservices, serverless, IaC, Terraform, security best practices.", "url": "", "date": ""},
]

_CONTRACT_ADZUNA: dict[str, str | None] = {
    "cdi": "permanent",
    "cdd": "contract",
    "stage": None,
    "alternance": None,
    "freelance": "contract",
    "temps_partiel": "part_time",
}

_EMPLOYMENT_DISPLAY: dict[str, str] = {
    "permanent": "CDI",
    "contract": "CDD",
    "part_time": "Temps partiel",
}

_DATE_ADZUNA: dict[str, int] = {
    "today": 1,
    "3days": 3,
    "week": 7,
    "month": 30,
}


def _clean_location(location: str) -> str:
    """Extract usable city/country from raw CV location strings.
    e.g. 'France - Mobilité nationale' → 'France'
         'Paris, Île-de-France'        → 'Paris'
    """
    if not location:
        return ""
    for sep in (" - ", ",", "/"):
        if sep in location:
            location = location.split(sep)[0]
    return location.strip()


async def _search_adzuna(
    client: httpx.AsyncClient,
    keyword: str,
    location: str,
    contract_type: str,
    remote: bool,
    date_posted: str,
    experience_level: str,  # noqa: ARG001 - handled by llm_reranker
) -> list[dict]:
    what = f"{keyword} remote" if remote else keyword

    params: dict = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "what": what,
        "results_per_page": 10,
    }
    if location:
        params["where"] = location
    if contract_type:
        adzuna_ct = _CONTRACT_ADZUNA.get(contract_type)
        if adzuna_ct:
            params["contract_type"] = adzuna_ct
    if date_posted and date_posted in _DATE_ADZUNA:
        params["max_days_old"] = _DATE_ADZUNA[date_posted]

    async with _ADZUNA_SEM:
        response = await client.get(
            f"https://api.adzuna.com/v1/api/jobs/{settings.ADZUNA_COUNTRY}/search/1",
            params=params,
            headers={"Content-Type": "application/json"},
            timeout=15.0,
        )
        await asyncio.sleep(0.3)
        response.raise_for_status()
    return [
        {
            "title": item.get("title", ""),
            "company": item.get("company", {}).get("display_name", ""),
            "location": _clean_location(item.get("location", {}).get("display_name", "")),
            "desc": (item.get("description", "") or ""),
            "url": item.get("redirect_url", ""),
            "date": item.get("created", ""),
            "contract_type": _EMPLOYMENT_DISPLAY.get(item.get("contract_type", ""), ""),
            "remote": "remote" in (item.get("location", {}).get("display_name", "") or "").lower(),
        }
        for item in response.json().get("results", [])
    ]


async def job_search_node(state: PipelineState) -> dict:
    """Node 4 - Search Adzuna with user filters applied."""
    keywords: list[str] = state.get("keywords") or []

    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        if settings.DEBUG:
            logger.warning("[job_search] Adzuna not configured - using mock data (DEBUG)")
            return {"jobs": _MOCK_JOBS}
        logger.warning("[job_search] Adzuna not configured - returning empty")
        return {"jobs": []}

    if not keywords:
        if settings.DEBUG:
            logger.warning("[job_search] No keywords - using mock data (DEBUG)")
            return {"jobs": _MOCK_JOBS}
        logger.warning("[job_search] No keywords - returning empty")
        return {"jobs": []}

    user_locations: list[str] = state.get("user_locations") or []
    contract_type: str = state.get("contract_type") or ""
    remote: bool = state.get("remote") or False
    date_posted: str = state.get("date_posted") or ""
    experience_level: str = state.get("experience_level") or ""

    # Priority: profile config location > CV location > no filter (all France)
    if user_locations:
        effective_locations = user_locations
    else:
        raw_cv_loc: str = (state.get("cv_json") or {}).get("location", "") or ""
        cleaned_cv_loc = _clean_location(raw_cv_loc)
        effective_locations = [cleaned_cv_loc] if cleaned_cv_loc else [""]

    logger.info(
        "[job_search] Keywords: %d | Locations: %s | contract=%s | remote=%s | date=%s | level=%s",
        len(keywords), effective_locations,
        contract_type or "all", remote, date_posted or "all", experience_level or "all",
    )

    t0 = time.monotonic()
    async with httpx.AsyncClient() as client:
        tasks = [
            _search_adzuna(client, kw, loc, contract_type, remote, date_posted, experience_level)
            for kw in keywords
            for loc in effective_locations
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.monotonic() - t0
    errors = sum(1 for r in results if isinstance(r, Exception))
    logger.info("[job_search] %d calls done in %.1fs (%d errors)", len(tasks), elapsed, errors)

    seen: set[tuple] = set()
    jobs: list[dict] = []
    for batch in results:
        if isinstance(batch, Exception):
            logger.warning("[job_search] Adzuna call failed: %s", batch)
            continue
        for job in batch:
            key = (job["title"].lower(), job["company"].lower())
            if key not in seen:
                seen.add(key)
                jobs.append(job)

    if not jobs:
        if settings.DEBUG:
            logger.warning("[job_search] Adzuna returned empty - using mock data (DEBUG)")
            return {"jobs": _MOCK_JOBS}
        logger.warning("[job_search] Adzuna returned empty")
        return {"jobs": []}

    logger.info("[job_search] %d unique jobs collected", len(jobs))
    return {"jobs": jobs}