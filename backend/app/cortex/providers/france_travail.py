import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.cortex.providers.base import JobProvider, RawJob
from app.logger import get_logger

logger = get_logger(__name__)

_TOKEN_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    "?realm=%2Fpartenaire"
)
_SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
_SCOPE = "api_offresdemploiv2 o2dsoffre"

# ROME codes covering the main knowledge-worker domains in France
ROME_CODES = [
    # IT / software
    "M1805",  # Études et développement informatique
    "M1801",  # Administration systèmes et réseaux
    "M1802",  # Expertise technico-fonctionnelle SI
    "M1804",  # Études et développement réseaux télécom
    "M1806",  # Conseil et MOA systèmes d'information
    "M1803",  # Direction des systèmes d'information
    # Marketing / communication / digital
    "E1401",  # Développement et promotion publicitaire
    "E1402",  # Élaboration de plan média
    "E1102",  # Gestion de contenus numériques
    # Finance / compta / contrôle
    "M1201",  # Analyse et ingénierie financière
    "M1202",  # Audit et contrôle comptable
    "M1204",  # Contrôle de gestion
    "C1301",  # Inspection et contrôle financier
    # RH
    "M1502",  # Développement des ressources humaines
    "M1501",  # Assistanat RH
    # Management / conseil
    "M1402",  # Conseil en organisation et management
    "M1404",  # Management et gestion de projet
    # Commerce / vente / business dev
    "M1701",  # Administration des ventes
    "M1702",  # Analyse de tendances
    "D1401",  # Assistanat commercial
]

# France Travail typeContrat → our schema
_CONTRACT_MAP: dict[str, str] = {
    "CDI": "CDI",
    "DIN": "CDI",   # CDI intérimaire
    "REP": "CDI",   # reprise
    "CDD": "CDD",
    "MIS": "CDD",   # intérim / mission
    "TTI": "CDD",
    "SAI": "CDD",   # saisonnier
    "CTT": "CDD",
    "DDU": "CDD",   # chantier
    "PRO": "Stage",  # professionnalisation
    "APP": "Stage",  # apprentissage
    "DEA": "Stage",
    "LIB": "Freelance",
    "FRA": "Freelance",
}

_PAGE_SIZE = 149   # 0-indexed: "0-149" = 150 results
_DELAY = 0.38      # ~2.6 req/s, safely under the 3 req/s limit


@dataclass
class _Token:
    value: str
    expires_at: datetime


class FranceTravailProvider(JobProvider):
    name = "france_travail"

    def __init__(self) -> None:
        self._token: _Token | None = None

    # ── OAuth2 ────────────────────────────────────────────────────────────────

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        now = datetime.now(timezone.utc)
        if self._token and self._token.expires_at > now + timedelta(seconds=30):
            return self._token.value

        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     settings.FRANCE_TRAVAIL_CLIENT_ID,
                "client_secret": settings.FRANCE_TRAVAIL_CLIENT_SECRET,
                "scope":         _SCOPE,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = _Token(
            value=data["access_token"],
            expires_at=now + timedelta(seconds=data.get("expires_in", 1499)),
        )
        logger.info("[france_travail] Token acquired (expires in %ds)", data.get("expires_in", 1499))
        return self._token.value

    # ── Main fetch ────────────────────────────────────────────────────────────

    async def fetch_jobs(self) -> list[RawJob]:
        if not (settings.FRANCE_TRAVAIL_CLIENT_ID and settings.FRANCE_TRAVAIL_CLIENT_SECRET):
            logger.warning("[france_travail] Credentials not configured - skipping")
            return []

        all_jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for rome in ROME_CODES:
                try:
                    jobs = await self._fetch_rome(client, rome)
                    all_jobs.extend(jobs)
                    logger.info("[france_travail] ROME=%s → %d jobs", rome, len(jobs))
                except Exception as exc:
                    logger.warning("[france_travail] ROME=%s failed: %s", rome, exc)
                await asyncio.sleep(_DELAY)

        logger.info("[france_travail] Total fetched: %d jobs across %d ROME codes", len(all_jobs), len(ROME_CODES))
        return all_jobs

    async def _fetch_rome(self, client: httpx.AsyncClient, rome: str) -> list[RawJob]:
        token = await self._get_token(client)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept":        "application/json",
        }

        resp = await client.get(
            _SEARCH_URL,
            headers=headers,
            params={
                "codeROME":      rome,
                "range":         f"0-{_PAGE_SIZE}",
                "publieeDepuis": 31,  # last month
            },
        )

        if resp.status_code == 204:
            return []

        resp.raise_for_status()
        resultats = resp.json().get("resultats", [])
        return [j for r in resultats if (j := self._normalize(r)) is not None]

    # ── Normalization ─────────────────────────────────────────────────────────

    def _normalize(self, r: dict) -> RawJob | None:
        title   = (r.get("intitule") or "").strip()
        company = ((r.get("entreprise") or {}).get("nom") or "").strip()
        location = ((r.get("lieuTravail") or {}).get("libelle") or "").strip()

        if not title:
            return None

        description = (r.get("description") or "")[:4000]

        url = ((r.get("origineOffre") or {}).get("urlOrigine") or "").strip()
        if not url:
            url = f"https://candidat.francetravail.fr/offres/recherche/detail/{r.get('id', '')}"

        contract_type = _CONTRACT_MAP.get(r.get("typeContrat", ""), "CDI")
        remote = r.get("teleTravail", "") == "IMPOSE"
        external_id = r.get("id", "")

        return RawJob(
            title=title,
            company=company or "Non précisé",
            location=location,
            description=description,
            url=url,
            contract_type=contract_type,
            remote=remote,
            source="france_travail",
            external_id=external_id,
        )
