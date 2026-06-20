import asyncio

import httpx

from app.config import settings
from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

_SEMAPHORE = asyncio.Semaphore(3)

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

_CONTRACT_JSEARCH: dict[str, str] = {
    "cdi": "FULLTIME",
    "cdd": "CONTRACTOR",
    "stage": "INTERN",
    "alternance": "INTERN",
    "freelance": "CONTRACTOR",
    "temps_partiel": "PARTTIME",
}

_CONTRACT_ADZUNA: dict[str, str | None] = {
    "cdi": "permanent",
    "cdd": "contract",
    "stage": None,
    "alternance": None,
    "freelance": "contract",
    "temps_partiel": "part_time",
}

# Normalize raw API employment type values to a display label
_EMPLOYMENT_DISPLAY: dict[str, str] = {
    # JSearch values
    "FULLTIME": "CDI",
    "PARTTIME": "Temps partiel",
    "CONTRACTOR": "Freelance / CDD",
    "INTERN": "Stage / Alternance",
    # Adzuna values
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

_EXPERIENCE_JSEARCH: dict[str, str] = {
    "junior": "under_3_years_experience",
    "senior": "more_than_3_years_experience",
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


async def _search_jsearch(
    client: httpx.AsyncClient,
    keyword: str,
    location: str,
    contract_type: str,
    remote: bool,
    date_posted: str,
    experience_level: str,
) -> list[dict]:
    query = f"{keyword} {location}".strip() if location else keyword

    params: dict = {"query": query, "num_pages": "1", "page": "1"}

    if remote:
        params["remote_jobs_only"] = "true"
    if contract_type and contract_type in _CONTRACT_JSEARCH:
        params["employment_types"] = _CONTRACT_JSEARCH[contract_type]
    if date_posted and date_posted != "all":
        params["date_posted"] = date_posted
    if experience_level and experience_level in _EXPERIENCE_JSEARCH:
        params["job_requirements"] = _EXPERIENCE_JSEARCH[experience_level]

    async with _SEMAPHORE:
        response = await client.get(
            "https://jsearch.p.rapidapi.com/search",
            params=params,
            headers={
                "X-RapidAPI-Key": settings.JSEARCH_API_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
            timeout=15.0,
        )
        response.raise_for_status()
    return [
        {
            "title": item.get("job_title", ""),
            "company": item.get("employer_name", ""),
            "location": item.get("job_city", "") or item.get("job_country", ""),
            "desc": (item.get("job_description", "") or "")[:500],
            "url": item.get("job_apply_link", ""),
            "date": item.get("job_posted_at_datetime_utc", ""),
            "contract_type": _EMPLOYMENT_DISPLAY.get(item.get("job_employment_type", ""), ""),
            "remote": bool(item.get("job_is_remote", False)),
        }
        for item in response.json().get("data", [])
    ]


async def _search_adzuna(
    client: httpx.AsyncClient,
    keyword: str,
    location: str,
    contract_type: str,
    remote: bool,
    date_posted: str,
    experience_level: str,  # noqa: ARG001 — handled by llm_reranker for all providers
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

    async with _SEMAPHORE:
        response = await client.get(
            f"https://api.adzuna.com/v1/api/jobs/{settings.ADZUNA_COUNTRY}/search/1",
            params=params,
            headers={"Content-Type": "application/json"},
            timeout=15.0,
        )
        response.raise_for_status()
    return [
        {
            "title": item.get("title", ""),
            "company": item.get("company", {}).get("display_name", ""),
            "location": item.get("location", {}).get("display_name", ""),
            "desc": (item.get("description", "") or "")[:500],
            "url": item.get("redirect_url", ""),
            "date": item.get("created", ""),
            "contract_type": _EMPLOYMENT_DISPLAY.get(item.get("contract_type", ""), ""),
            "remote": "remote" in (item.get("location", {}).get("display_name", "") or "").lower(),
        }
        for item in response.json().get("results", [])
    ]


def _active_providers() -> list[str]:
    providers = []
    if settings.JSEARCH_API_KEY:
        providers.append("jsearch")
    if settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY:
        providers.append("adzuna")
    return providers


async def job_search_node(state: PipelineState) -> dict:
    """Node 4 — Search all active providers with user filters applied."""
    keywords: list[str] = state.get("keywords") or []
    providers = _active_providers()

    user_locations: list[str] = state.get("user_locations") or []
    contract_type: str = state.get("contract_type") or ""
    remote: bool = state.get("remote") or False
    date_posted: str = state.get("date_posted") or ""
    experience_level: str = state.get("experience_level") or ""

    if user_locations:
        effective_locations = user_locations
    else:
        raw_location: str = (state.get("cv_json") or {}).get("location", "") or ""
        cleaned = _clean_location(raw_location)
        effective_locations = [cleaned] if cleaned else [""]

    if not providers or not keywords:
        if settings.DEBUG:
            logger.warning("[job_search] No active providers or keywords — using mock data (DEBUG)")
            return {"jobs": _MOCK_JOBS}
        logger.warning("[job_search] No active providers or keywords — returning empty")
        return {"jobs": []}

    logger.info(
        "[job_search] Providers: %s | Keywords: %d | Locations: %s | contract=%s | remote=%s | date=%s | level=%s | Total calls: %d",
        providers, len(keywords), effective_locations,
        contract_type or "all", remote, date_posted or "all", experience_level or "all",
        len(keywords) * len(effective_locations) * len(providers),
    )

    async with httpx.AsyncClient() as client:
        tasks = []
        for kw in keywords:
            for loc in effective_locations:
                for provider in providers:
                    if provider == "jsearch":
                        tasks.append(_search_jsearch(client, kw, loc, contract_type, remote, date_posted, experience_level))
                    elif provider == "adzuna":
                        tasks.append(_search_adzuna(client, kw, loc, contract_type, remote, date_posted, experience_level))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    seen: set[tuple] = set()
    jobs: list[dict] = []
    for batch in results:
        if isinstance(batch, Exception):
            logger.warning("[job_search] Provider call failed: %s", batch)
            continue
        for job in batch:
            key = (job["title"].lower(), job["company"].lower())
            if key not in seen:
                seen.add(key)
                jobs.append(job)

    if not jobs:
        if settings.DEBUG:
            logger.warning("[job_search] All providers returned empty — using mock data (DEBUG)")
            return {"jobs": _MOCK_JOBS}
        logger.warning("[job_search] All providers returned empty")
        return {"jobs": []}

    logger.info("[job_search] %d unique jobs collected", len(jobs))
    return {"jobs": jobs}