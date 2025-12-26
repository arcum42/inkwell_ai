#!/usr/bin/env python
"""Pytest: verify RAG refactor maintains backward compatibility."""

def test_rag_import_paths():
    """Both new and legacy import paths should resolve to the same class."""
    from core.rag import RAGEngine, MarkdownChunker, QueryCache, ContextOptimizer
    from core.rag_engine import RAGEngine as RAGEngineCompat

    # Basic existence checks for auxiliary classes
    assert RAGEngine is not None
    assert MarkdownChunker is not None
    assert QueryCache is not None
    assert ContextOptimizer is not None

    # Backward compatibility: class identity must match
    assert RAGEngine is RAGEngineCompat
