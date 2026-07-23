"""Small deterministic processors used by the fixed knowledge pipeline."""

from __future__ import annotations

import hashlib
from typing import Protocol, Sequence

from app.knowledge.context import ProcessorContext
from app.knowledge.events import CacheHit, CacheMiss, ChunkCreated, EmbeddingGenerated
from app.knowledge.models import ChunkAsset, EmbeddingAsset, PageAsset
from app.knowledge.providers import EmbeddingProvider


class Processor(Protocol):
    name: str
    version: str


class ChunkProcessor:
    name = "chunk"
    version = "1.0"

    async def process(self, pages: Sequence[PageAsset], context: ProcessorContext) -> list[ChunkAsset]:
        chunks: list[ChunkAsset] = []
        size = context.settings.chunk_size_words
        overlap = context.settings.chunk_overlap_words
        step = max(1, size - overlap)
        for page in pages:
            words = page.content.split()
            for ordinal, start in enumerate(range(0, len(words), step)):
                text = " ".join(words[start : start + size]).strip()
                if not text:
                    continue
                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                chunk = ChunkAsset(
                    chunk_id=f"{page.page_id}:{ordinal}:{content_hash[:12]}",
                    page_id=page.page_id,
                    ordinal=ordinal,
                    text=text,
                    token_count=len(text.split()),
                    content_hash=content_hash,
                )
                chunks.append(chunk)
                context.events.emit(ChunkCreated(stage=self.name, chunk_id=chunk.chunk_id, page_id=page.page_id))
                if start + size >= len(words):
                    break
        return chunks


class EmbeddingProcessor:
    name = "embedding"
    version = "1.0"

    def __init__(self, provider: EmbeddingProvider, cache) -> None:
        self.provider = provider
        self.cache = cache

    async def process(self, chunks: Sequence[ChunkAsset], context: ProcessorContext) -> list[EmbeddingAsset]:
        embeddings: list[EmbeddingAsset] = []
        missing: list[tuple[ChunkAsset, str]] = []
        for chunk in chunks:
            key = self.cache.fingerprint(chunk.content_hash, self.name, self.version, self.provider.profile_id)
            cached = self.cache.get_json(key)
            if cached:
                context.events.emit(CacheHit(stage=self.name, key=key, record_id=chunk.chunk_id))
                embeddings.append(EmbeddingAsset.model_validate(cached))
            else:
                context.events.emit(CacheMiss(stage=self.name, key=key, record_id=chunk.chunk_id))
                missing.append((chunk, key))
        for start in range(0, len(missing), context.settings.batch_size):
            batch = missing[start : start + context.settings.batch_size]
            vectors = await self.provider.embed([chunk.text for chunk, _ in batch])
            for (chunk, key), vector in zip(batch, vectors, strict=True):
                asset = EmbeddingAsset(
                    chunk_id=chunk.chunk_id,
                    profile_id=self.provider.profile_id,
                    dimension=len(vector),
                    vector=vector,
                    processing_fingerprint=key,
                )
                self.cache.put_json(key, asset.model_dump(mode="json"))
                embeddings.append(asset)
                context.events.emit(EmbeddingGenerated(stage=self.name, chunk_id=chunk.chunk_id, profile_id=self.provider.profile_id))
        return embeddings
