from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawJob:
    title: str
    company: str
    location: str
    description: str
    url: str
    contract_type: str   # CDI | CDD | Freelance | Stage | Alternance
    remote: bool
    source: str          # france_travail | greenhouse | lever
    external_id: str     # provider-unique ID used for deduplication


class JobProvider(ABC):
    name: str

    @abstractmethod
    async def fetch_jobs(self) -> list[RawJob]:
        """Fetch and normalize jobs from this source."""
        ...