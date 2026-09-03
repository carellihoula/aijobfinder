"""Langfuse tracing - graceful no-op when LANGFUSE_PUBLIC_KEY isn't set, same
pattern as CORTEX_DATABASE_URL (see cortex/db.py). Two entry points:

- `get_langfuse_callbacks()` - for ChatOpenAI/structured-output calls, which
  support LangChain's callback mechanism natively.
- `traced_embedding()` - for OpenAIEmbeddings calls, which don't: LangChain's
  `Embeddings` base class has no callback support (unlike ChatModels), a
  documented gap in Langfuse's LangChain integration. Wraps the call in a
  manual generation span instead.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from functools import lru_cache

import tiktoken

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _client():
    """Explicitly-configured Langfuse client, or None if unconfigured.

    Deliberately NOT relying on the SDK's ambient env-var auto-detection:
    pydantic-settings parses `.env` into `settings` without ever exporting
    those values into `os.environ`, so `langfuse.get_client()` called bare
    would silently see no credentials and disable itself even with valid
    keys in `.env` - passing them explicitly here is required."""
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        logger.info("[observability] Langfuse not configured - tracing disabled")
        return None
    from langfuse import Langfuse
    logger.info("[observability] Langfuse tracing enabled - host=%s", settings.LANGFUSE_HOST)
    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )


def get_langfuse_callbacks() -> list:
    """Pass as `callbacks=...` to a ChatOpenAI constructor - empty list (no-op)
    when Langfuse isn't configured."""
    if _client() is None:
        return []
    from langfuse.langchain import CallbackHandler
    return [CallbackHandler()]


def count_tokens(texts: list[str], model: str) -> int:
    """Best-effort input token count for embedding calls, which return no
    usage data - falls back to cl100k_base for models tiktoken doesn't know
    (e.g. text-embedding-3-small is covered, but stay defensive)."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return sum(len(encoding.encode(t)) for t in texts if t)


class _NullSpan:
    def update(self, **_kwargs) -> None:
        pass


class _NullContext(AbstractContextManager):
    def __enter__(self) -> _NullSpan:
        return _NullSpan()

    def __exit__(self, *exc) -> bool:
        return False


def traced_embedding(name: str, model: str) -> AbstractContextManager:
    """Context manager wrapping an embeddings call as a Langfuse generation.
    No-op when Langfuse isn't configured. Usage:

        with traced_embedding("cortex_search.embed_cv", model) as span:
            vectors = await embedder.aembed_documents(texts)
            span.update(usage_details={"input": count_tokens(texts, model)})
    """
    client = _client()
    if client is None:
        return _NullContext()
    return client.start_as_current_observation(as_type="generation", name=name, model=model)