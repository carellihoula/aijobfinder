import asyncio
import re

import httpx

from app.cortex.providers.base import JobProvider, RawJob
from app.logger import get_logger

logger = get_logger(__name__)

_API_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
_DELAY = 0.5  # seconds between company requests

# French companies (or companies with major French offices) confirmed on Greenhouse.
# Slug = the identifier in boards-api.greenhouse.io/v1/boards/{slug}/jobs
# To add a company: verify the slug works before adding (404 = wrong ATS or slug).
FRENCH_COMPANIES: list[tuple[str, str]] = [
    # (slug, display_name)
    ("doctolib",   "Doctolib"),
    ("dataiku",    "Dataiku"),
    ("algolia",    "Algolia"),
]


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class GreenhouseProvider(JobProvider):
    name = "greenhouse"

    async def fetch_jobs(self) -> list[RawJob]:
        all_jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for slug, company_name in FRENCH_COMPANIES:
                try:
                    jobs = await self._fetch_company(client, slug, company_name)
                    all_jobs.extend(jobs)
                    logger.info("[greenhouse] %s → %d jobs", company_name, len(jobs))
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        logger.debug("[greenhouse] %s (slug=%s) not found — skipping", company_name, slug)
                    else:
                        logger.warning("[greenhouse] %s failed: %s", company_name, exc)
                except Exception as exc:
                    logger.warning("[greenhouse] %s failed: %s", company_name, exc)
                await asyncio.sleep(_DELAY)

        logger.info("[greenhouse] Total fetched: %d jobs", len(all_jobs))
        return all_jobs

    async def _fetch_company(self, client: httpx.AsyncClient, slug: str, company_name: str) -> list[RawJob]:
        resp = await client.get(_API_URL.format(slug=slug))
        resp.raise_for_status()
        data = resp.json()

        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            job = self._normalize(item, company_name, slug)
            if job:
                jobs.append(job)
        return jobs

    def _normalize(self, item: dict, company_name: str, slug: str) -> RawJob | None:
        title = (item.get("title") or "").strip()
        if not title:
            return None

        location = ((item.get("location") or {}).get("name") or "").strip()
        description = _strip_html(item.get("content") or "")[:4000]
        url = item.get("absolute_url") or f"https://boards.greenhouse.io/{slug}/jobs/{item.get('id', '')}"
        external_id = str(item.get("id", ""))

        return RawJob(
            title=title,
            company=company_name,
            location=location or "France",
            description=description,
            url=url,
            contract_type="CDI",   # Greenhouse doesn't expose contract type in the public API
            remote=_is_remote(location, title),
            source="greenhouse",
            external_id=external_id,
        )


def _is_remote(location: str, title: str) -> bool:
    needle = "remote"
    return needle in location.lower() or needle in title.lower()