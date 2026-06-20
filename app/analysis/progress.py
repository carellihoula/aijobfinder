"""In-process event bus for streaming pipeline progress to SSE clients."""
import asyncio
from collections import defaultdict
from typing import AsyncIterator

_queues:  dict[str, list[asyncio.Queue]] = defaultdict(list)
_history: dict[str, list[dict]]          = defaultdict(list)  # replay buffer

NODE_LABELS: dict[str, str] = {
    "pdf_parser":         "Lecture du CV",
    "cv_structurer":      "Analyse du profil",
    "cortex_search":      "Recherche Cortex",
    "keyword_extractor":  "Extraction des mots-clés",
    "job_search":         "Recherche d'offres",
    "cortex_feed":        "Mise à jour Cortex",
    "prepare_retry":      "Nouvelle tentative",
    "embeddings_filter":  "Filtrage sémantique",
    "llm_reranker":       "Classement IA",
    "report_generator":   "Génération du rapport",
}


def publish(analysis_id: str, node: str) -> None:
    event = {"node": node, "label": NODE_LABELS.get(node, node)}
    _history[analysis_id].append(event)          # always store in history
    for q in _queues.get(analysis_id, []):       # push to live subscribers
        q.put_nowait(event)


def publish_done(analysis_id: str) -> None:
    done = {"done": True}
    _history[analysis_id].append(done)
    for q in _queues.get(analysis_id, []):
        q.put_nowait(done)
    _queues.pop(analysis_id, None)


async def subscribe(analysis_id: str, timeout: int = 600) -> AsyncIterator[dict]:
    q: asyncio.Queue = asyncio.Queue()

    # Replay all events published before this subscriber connected
    for past in _history.get(analysis_id, []):
        q.put_nowait(past)

    _queues[analysis_id].append(q)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=timeout)
            except asyncio.TimeoutError:
                break
            yield event
            if event.get("done"):
                break
    finally:
        try:
            _queues[analysis_id].remove(q)
        except (ValueError, KeyError):
            pass


def has_history(analysis_id: str) -> bool:
    return bool(_history.get(analysis_id))


def clear(analysis_id: str) -> None:
    """Clean up history after analysis is done (called on pipeline completion)."""
    _history.pop(analysis_id, None)
    _queues.pop(analysis_id, None)