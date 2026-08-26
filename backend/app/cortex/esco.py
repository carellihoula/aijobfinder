"""
ESCO REST API client — European Skills, Competencies, Qualifications and Occupations.
https://esco.ec.europa.eu/api

Fetches occupation titles from the official EU taxonomy to use as Cortex seed keywords.
NOT wired into the ingestion pipeline.

Manual usage:
    from app.cortex.esco import fetch_keywords_by_domain, fetch_all_keywords

CLI usage (prints a summary table):
    python -m app.cortex.esco
"""
from __future__ import annotations

import asyncio

import httpx

from app.logger import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://esco.ec.europa.eu/api"
_LANGUAGE = "fr"
_PAGE_SIZE = 100
_MAX_PAGES = 10  # safety cap — 1 000 occupations per ISCO group max
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)

# ISCO-08 group codes mapped to our Cortex domains.
# Reference: https://www.ilo.org/public/english/bureau/stat/isco/isco08/
_ISCO_BASE_URI = "http://data.europa.eu/esco/isco"

_DOMAIN_TO_ISCO_GROUPS: dict[str, list[str]] = {
    "tech_software":          ["C251", "C252"],   # Software devs + DB/network professionals
    "tech_data":              ["C251"],            # Overlaps software; data roles live here
    "tech_infra":             ["C252"],            # ICT network & systems professionals
    "tech_security":          ["C252"],            # Cybersecurity subset of C252
    "tech_product":           ["C251"],            # Product/UX-adjacent dev roles
    "tech_design":            ["C216", "C265"],    # Architects + creative/media designers
    "finance_banking":        ["C241"],            # Finance professionals
    "marketing_sales":        ["C243"],            # Sales, marketing & PR professionals
    "hr_legal":               ["C242", "C261"],    # HR + legal professionals
    "engineering_industry":   ["C211", "C212", "C213", "C214", "C215"],  # All engineering branches
    "supply_chain":           ["C133"],            # Supply, distribution & production managers
    "healthcare":             ["C221", "C222", "C223", "C224", "C225"],  # All health professionals
    "education_research":     ["C231", "C232", "C235"],  # Teachers + research professionals
    "consulting_management":  ["C121", "C122", "C123"],  # Business & admin managers
    "construction_real_estate": ["C216", "C311"], # Architects + physical/engineering technicians
    "communication_media":    ["C264", "C265"],   # Authors, journalists, creative/media workers
}


async def _fetch_group_occupations(
    client: httpx.AsyncClient,
    isco_code: str,
) -> list[str]:
    """Return all occupation preferred labels within an ISCO-08 group (paginated)."""
    uri = f"{_ISCO_BASE_URI}/{isco_code}"
    titles: list[str] = []

    for page in range(_MAX_PAGES):
        offset = page * _PAGE_SIZE
        try:
            resp = await client.get(
                f"{_BASE_URL}/resource/ISCOGroup/hasOccupation",
                params={
                    "language": _LANGUAGE,
                    "uri": uri,
                    "limit": _PAGE_SIZE,
                    "offset": offset,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("[esco] HTTP error for ISCO %s (offset=%d): %s", isco_code, offset, exc)
            break

        data = resp.json()
        occupations: list[dict] = data.get("_embedded", {}).get("occupation", [])

        if not occupations:
            break

        for occ in occupations:
            title = (occ.get("title") or "").strip().lower()
            if title:
                titles.append(title)

        total: int = data.get("total", 0)
        if offset + _PAGE_SIZE >= total:
            break

    logger.debug("[esco] ISCO %s → %d occupation titles", isco_code, len(titles))
    return titles


async def fetch_keywords_by_domain(domain: str) -> list[str]:
    """
    Return deduplicated ESCO occupation titles for a given Cortex domain.

    Args:
        domain: one of the keys in _DOMAIN_TO_ISCO_GROUPS

    Returns:
        Sorted, deduplicated list of lowercase occupation titles.

    Raises:
        ValueError: if the domain is not recognized.
    """
    isco_groups = _DOMAIN_TO_ISCO_GROUPS.get(domain)
    if not isco_groups:
        raise ValueError(
            f"Unknown domain {domain!r}. Available: {sorted(_DOMAIN_TO_ISCO_GROUPS)}"
        )

    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        results = await asyncio.gather(
            *[_fetch_group_occupations(client, code) for code in isco_groups],
            return_exceptions=True,
        )

    for r in results:
        if isinstance(r, Exception):
            logger.warning("[esco] group fetch failed: %s", r)
        else:
            seen.update(r)

    return sorted(seen)


async def fetch_all_keywords() -> dict[str, list[str]]:
    """
    Fetch ESCO keywords for every Cortex domain.

    Returns:
        {domain: [sorted occupation titles]}
        Domains that fail are included with an empty list (not raised).
    """
    result: dict[str, list[str]] = {}

    for domain in _DOMAIN_TO_ISCO_GROUPS:
        try:
            titles = await fetch_keywords_by_domain(domain)
            result[domain] = titles
            logger.info("[esco] %-30s → %d keywords", domain, len(titles))
        except Exception as exc:
            logger.error("[esco] failed for domain %s: %s", domain, exc)
            result[domain] = []

    return result


if __name__ == "__main__":
    async def _main() -> None:
        print("Fetching ESCO occupation keywords …\n")
        keywords = await fetch_all_keywords()
        total = sum(len(v) for v in keywords.values())
        for domain, titles in keywords.items():
            print(f"  {domain:<32} {len(titles):>4} keywords")
        print(f"\n  {'TOTAL':<32} {total:>4} keywords across {len(keywords)} domains")

    asyncio.run(_main())