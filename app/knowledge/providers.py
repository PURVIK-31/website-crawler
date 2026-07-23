"""Narrow provider interfaces; only configured concrete providers are injected."""

from __future__ import annotations

import hashlib
import asyncio
from typing import Protocol, Sequence

from app.knowledge.errors import ConfigurationError


class EmbeddingProvider(Protocol):
    profile_id: str

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...


class FakeEmbeddingProvider:
    """Deterministic test/development provider, not semantic embeddings."""

    profile_id = "fake-v1"
    dimension = 8

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        result: list[tuple[float, ...]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            result.append(tuple(round(byte / 255.0, 8) for byte in digest[: self.dimension]))
        return result


class SentenceTransformersProvider:
    def __init__(self, model_name: str, profile_id: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ConfigurationError("Install sentence-transformers to use this embedding provider.") from exc
        self.profile_id = profile_id
        self._model = SentenceTransformer(model_name)

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        vectors = await asyncio.to_thread(self._model.encode, list(texts), normalize_embeddings=True)
        return [tuple(float(value) for value in vector) for vector in vectors]
