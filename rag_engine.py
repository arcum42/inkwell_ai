"""Backward-compatibility shim for pre-refactor imports.

This module preserves the legacy `rag_engine` import path by re-exporting
classes from the refactored package under `core.rag_engine`.
"""
from __future__ import annotations

from core.rag_engine import (
    RAGEngine,
    MarkdownChunker,
    QueryCache,
    ContextOptimizer,
)

__all__ = [
    "RAGEngine",
    "MarkdownChunker",
    "QueryCache",
    "ContextOptimizer",
]
