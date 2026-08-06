import asyncio

import pandas as pd
from jobspy import scrape_jobs

from app.cortex.providers.base import JobProvider, RawJob
from app.cortex.seeds import SEED_KEYWORDS_BY_DOMAIN
from app.logger import get_logger

logger = get_logger(__name__)

_LOCATION = "France"
_SITE_TIMEOUT = 240  # seconds — a hung call is skipped, not awaited forever
_DELAY = 1.0         # between calls, be a reasonable citizen

# No search_term = the site's generic "browse jobs" feed for the location, unfiltered by
# domain/keyword — Indeed and LinkedIn both support this (real job-board browse pages).
_BROAD_SITE_QUERIES: list[tuple[str, dict]] = [
    ("indeed",   {"results_wanted": 500}),
    ("linkedin", {"results_wanted": 300}),
]

# Google Jobs isn't a job board — it's Google Search's "jobs" panel, triggered by a search
# query. There's no "browse everything" mode, so it needs an actual term. One representative
# keyword per seed domain keeps it broad without looping all 130+ keywords.
_GOOGLE_SEARCH_TERMS = [keywords[0] for keywords in SEED_KEYWORDS_BY_DOMAIN.values()]
_GOOGLE_RESULTS_PER_TERM = 20

# JobSpy job_type → our schema
_JOB_TYPE_MAP: dict[str, str] = {
    "fulltime": "CDI",
    "parttime": "CDD",
    "internship": "Stage",
    "contract": "Freelance",
    "temporary": "CDD",
}


def _s(val) -> str:
    """Safe string coercion — pandas represents missing values as NaN (float), which
    would otherwise stringify to the literal "nan"."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val).strip()


class JobSpyProvider(JobProvider):
    """Scrapes Indeed, LinkedIn and Google Jobs via the open-source `python-jobspy` package.

    Indeed and LinkedIn are pulled with no search_term — their generic "browse jobs in
    France" feed, unfiltered by domain/keyword. Google Jobs has no such feed (it's a search
    panel, not a job board), so it's queried once per seed-domain keyword instead.

    Every call (per site, or per Google search term) is isolated with its own timeout and
    try/except — a hang or a block (LinkedIn and Indeed are the most prone to this) is logged
    and skipped, it never aborts the rest.
    """

    name = "jobspy"

    async def fetch_jobs(self) -> list[RawJob]:
        all_jobs: list[RawJob] = []

        for site, extra_kwargs in _BROAD_SITE_QUERIES:
            all_jobs.extend(await self._run(site, extra_kwargs, label=site))
            await asyncio.sleep(_DELAY)

        for term in _GOOGLE_SEARCH_TERMS:
            extra_kwargs = {"results_wanted": _GOOGLE_RESULTS_PER_TERM, "google_search_term": f"{term} jobs near France"}
            all_jobs.extend(await self._run("google", extra_kwargs, label=f"google/{term!r}"))
            await asyncio.sleep(_DELAY)

        logger.info("[jobspy] Total fetched: %d jobs", len(all_jobs))
        return all_jobs

    async def _run(self, site: str, extra_kwargs: dict, label: str) -> list[RawJob]:
        try:
            df = await asyncio.wait_for(
                asyncio.to_thread(self._scrape, site, extra_kwargs),
                timeout=_SITE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[jobspy] %s timed out after %ds — skipping", label, _SITE_TIMEOUT)
            return []
        except Exception as exc:
            logger.warning("[jobspy] %s failed: %s — skipping", label, exc)
            return []

        if df is None or df.empty:
            return []

        jobs = [j for _, row in df.iterrows() if (j := self._normalize(row, site))]
        logger.info("[jobspy] %s → %d jobs", label, len(jobs))
        return jobs

    def _scrape(self, site: str, extra_kwargs: dict) -> pd.DataFrame:
        kwargs: dict = dict(
            site_name=[site],
            location=_LOCATION,
            country_indeed="france",
            description_format="markdown",
            **extra_kwargs,
        )
        return scrape_jobs(**kwargs)

    def _normalize(self, row, site: str) -> RawJob | None:
        title = _s(row.get("title"))
        company = _s(row.get("company"))
        if not title or not company:
            return None

        job_type = _s(row.get("job_type")).lower()
        contract_type = _JOB_TYPE_MAP.get(job_type, "CDI")

        url = _s(row.get("job_url"))
        external_id = _s(row.get("id")) or url
        location = _s(row.get("location")) or "France"
        description = _s(row.get("description"))[:4000]
        remote = row.get("is_remote") is True

        return RawJob(
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            contract_type=contract_type,
            remote=remote,
            source=f"jobspy_{site}",
            external_id=external_id,
        )