"""Embedding service — Voyage AI for vector embeddings."""

import logging
from typing import Optional

import voyageai

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Abstracted embedding provider. Default: Voyage AI.

    Interface is provider-agnostic so it can be swapped to
    OpenAI, Cohere, or a local model by implementing embed().
    """

    def __init__(self):
        self._client: Optional[voyageai.AsyncClient] = None

    @property
    def client(self) -> voyageai.AsyncClient:
        if self._client is None:
            if not settings.VOYAGE_API_KEY:
                raise RuntimeError("VOYAGE_API_KEY is not configured")
            self._client = voyageai.AsyncClient(api_key=settings.VOYAGE_API_KEY)
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate a vector embedding for the given text.

        Returns a list of floats with dimension matching VOYAGE_EMBEDDING_DIMENSIONS.
        """
        result = await self.client.embed(
            texts=[text],
            model=settings.VOYAGE_EMBEDDING_MODEL,
        )
        vector = result.embeddings[0]
        logger.debug(f"[Embedding] Generated {len(vector)}-dim vector")
        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single API call."""
        result = await self.client.embed(
            texts=texts,
            model=settings.VOYAGE_EMBEDDING_MODEL,
        )
        return result.embeddings


embedding_service = EmbeddingService()
