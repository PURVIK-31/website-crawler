"""Non-secret settings for optional knowledge ingestion."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    storage_root: Path = Path("storage")
    enable_embeddings: bool = False
    embedding_profile_id: str = "fake-v1"
    chunk_size_words: int = Field(default=300, ge=1, le=2_000)
    chunk_overlap_words: int = Field(default=40, ge=0, le=500)
    batch_size: int = Field(default=64, ge=1, le=1_000)

    @classmethod
    def from_env(cls) -> "KnowledgeSettings":
        return cls(
            storage_root=Path(os.environ.get("KNOWLEDGE_STORAGE_ROOT", "storage")),
            enable_embeddings=os.environ.get("KNOWLEDGE_ENABLE_EMBEDDINGS", "false").lower() == "true",
            embedding_profile_id=os.environ.get("KNOWLEDGE_EMBEDDING_PROFILE", "fake-v1"),
            chunk_size_words=int(os.environ.get("KNOWLEDGE_CHUNK_SIZE_WORDS", "300")),
            chunk_overlap_words=int(os.environ.get("KNOWLEDGE_CHUNK_OVERLAP_WORDS", "40")),
            batch_size=int(os.environ.get("KNOWLEDGE_BATCH_SIZE", "64")),
        )
