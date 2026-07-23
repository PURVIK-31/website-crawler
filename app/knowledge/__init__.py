"""Versioned, optional knowledge-ingestion capabilities.

This package deliberately depends on the legacy crawler, but legacy crawler
modules do not depend on this package. Import concrete modules directly to
avoid eager provider and crawler imports at package-import time.
"""
