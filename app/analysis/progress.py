"""Pipeline progress events via Redis Pub/Sub.

Publish side  (Celery worker) : await publish(analysis_id, node_name)
Subscribe side (FastAPI SSE)  : async for event in subscribe(analysis_id): ...

History is stored in a Redis LIST (1h TTL) so late SSE subscribers
receive all past events without missing any — race-condition safe because
we subscribe to the channel BEFORE reading history.
"""
import asyncio
import json
from typing import AsyncIterator

import redis.asyncio as aioredis

from app.config import settings

_CHANNEL     = "pipeline:progress:{}"
_HISTORY     = "pipeline:history:{}"
_HISTORY_TTL = 3600  # 1 hour

NODE_LABELS: dict[str, str] = {
    "pdf_parser":        "Lecture du CV",
    "cv_structurer":     "Analyse du profil",
    "cortex_search":     "Recherche Cortex",
    "keyword_extractor": "Extraction des mots-clés",
    "job_search":        "Recherche d'offres",
    "cortex_feed":       "Mise à jour Cortex",
    "prepare_retry":     "Nouvelle tentative",
    "embeddings_filter": "Filtrage sémantique",
    "llm_reranker":      "Classement IA",
    "report_generator":  "Génération du rapport",
}


def _r() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def publish(analysis_id: str, node: str) -> None:
    event = {"node": node, "label": NODE_LABELS.get(node, node)}
    raw = json.dumps(event)
    async with _r() as r:
        pipe = r.pipeline()
        pipe.rpush(_HISTORY.format(analysis_id), raw)
        pipe.expire(_HISTORY.format(analysis_id), _HISTORY_TTL)
        pipe.publish(_CHANNEL.format(analysis_id), raw)
        await pipe.execute()


async def publish_done(analysis_id: str) -> None:
    raw = json.dumps({"done": True})
    async with _r() as r:
        pipe = r.pipeline()
        pipe.rpush(_HISTORY.format(analysis_id), raw)
        pipe.expire(_HISTORY.format(analysis_id), _HISTORY_TTL)
        pipe.publish(_CHANNEL.format(analysis_id), raw)
        await pipe.execute()


async def subscribe(analysis_id: str, timeout: int = 600) -> AsyncIterator[dict]:
    r = _r()
    pubsub = r.pubsub()

    # Subscribe BEFORE reading history — avoids the race where done is published
    # between lrange and subscribe
    await pubsub.subscribe(_CHANNEL.format(analysis_id))

    try:
        # Replay all past events (pipeline may have already progressed)
        past = await r.lrange(_HISTORY.format(analysis_id), 0, -1)
        for raw in past:
            event = json.loads(raw)
            yield event
            if event.get("done"):
                return  # Pipeline already finished, nothing more to wait for

        # Listen for live events
        async with asyncio.timeout(timeout):
            async for message in pubsub.listen():
                if message["type"] == "message":
                    event = json.loads(message["data"])
                    yield event
                    if event.get("done"):
                        break

    except asyncio.TimeoutError:
        pass
    finally:
        await pubsub.unsubscribe(_CHANNEL.format(analysis_id))
        await r.aclose()


async def has_history(analysis_id: str) -> bool:
    async with _r() as r:
        return await r.llen(_HISTORY.format(analysis_id)) > 0


async def clear(analysis_id: str) -> None:
    async with _r() as r:
        await r.delete(_HISTORY.format(analysis_id))
