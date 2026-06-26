import asyncio
import re
from datetime import datetime, timezone

import httpx

from app.cortex.providers.base import JobProvider, RawJob
from app.logger import get_logger

logger = get_logger(__name__)

_API_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"
_DELAY = 0.5

# French companies confirmed on Lever.
# To add a company: verify the slug works before adding (404 = wrong ATS or slug).
FRENCH_COMPANIES: list[tuple[str, str]] = [
    # (slug, display_name)
    ("malt",    "Malt"),
    ("pigment", "Pigment"),
    ("ogury",   "Ogury"),
]

# Lever "commitment" → our contract type
_COMMITMENT_MAP: dict[str, str] = {
    "Full-time":   "CDI",
    "Part-time":   "CDD",
    "Internship":  "Stage",
    "Contract":    "Freelance",
    "Temporary":   "CDD",
}


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class LeverProvider(JobProvider):
    name = "lever"

    async def fetch_jobs(self) -> list[RawJob]:
        all_jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for slug, company_name in FRENCH_COMPANIES:
                try:
                    jobs = await self._fetch_company(client, slug, company_name)
                    all_jobs.extend(jobs)
                    logger.info("[lever] %s → %d jobs", company_name, len(jobs))
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        logger.debug("[lever] %s (slug=%s) not found — skipping", company_name, slug)
                    else:
                        logger.warning("[lever] %s failed: %s", company_name, exc)
                except Exception as exc:
                    logger.warning("[lever] %s failed: %s", company_name, exc)
                await asyncio.sleep(_DELAY)

        logger.info("[lever] Total fetched: %d jobs", len(all_jobs))
        return all_jobs

    async def _fetch_company(self, client: httpx.AsyncClient, slug: str, company_name: str) -> list[RawJob]:
        resp = await client.get(_API_URL.format(slug=slug))
        resp.raise_for_status()
        postings = resp.json()
        if not isinstance(postings, list):
            return []

        jobs: list[RawJob] = []
        for item in postings:
            job = self._normalize(item, company_name)
            if job:
                jobs.append(job)
        return jobs

    def _normalize(self, item: dict, company_name: str) -> RawJob | None:
        title = (item.get("text") or "").strip()
        if not title:
            return None

        categories = item.get("categories") or {}
        location   = (categories.get("location") or "").strip()
        commitment = categories.get("commitment") or ""
        contract_type = _COMMITMENT_MAP.get(commitment, "CDI")

        # Lever description is in `description` (plain text) or `descriptionPlain`
        description = _strip_html(
            item.get("description") or item.get("descriptionPlain") or ""
        )[:4000]

        url = item.get("hostedUrl") or ""
        external_id = item.get("id") or ""
        remote = _is_remote(location, title)

        return RawJob(
            title=title,
            company=company_name,
            location=location or "France",
            description=description,
            url=url,
            contract_type=contract_type,
            remote=remote,
            source="lever",
            external_id=external_id,
        )


def _is_remote(location: str, title: str) -> bool:
    needle = "remote"
    return needle in location.lower() or needle in title.lower()