"""Typed errors used by the knowledge ingestion boundary."""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base exception for v2 knowledge processing failures."""


class ConfigurationError(KnowledgeError):
    """Raised when an optional capability is requested without configuration."""


class ProviderError(KnowledgeError):
    """Raised when a provider cannot complete a request."""


class StorageError(KnowledgeError):
    """Raised when a durable asset or cache operation fails."""


class AssetNotFoundError(KnowledgeError):
    """Raised when an asset/version cannot be located."""
