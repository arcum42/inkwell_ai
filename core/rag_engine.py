"""Backward compatibility wrapper for RAG module.

This file provides backward compatibility for code importing from core.rag_engine.
All functionality has been refactored into the core.rag submodule.

For new code, import directly from core.rag:
    from core.rag import RAGEngine
    
For existing code, this import still works:
    from core.rag_engine import RAGEngine
"""

# Import all public APIs from the new location
from core.rag import (
    RAGEngine,
    MarkdownChunker,
    QueryCache,
    ContextOptimizer,
    SimpleBM25,
    ChunkMetadata,
    TOKENS_PER_CHAR,
    MIN_CHUNK_TOKENS,
    DEFAULT_CHUNK_TOKENS,
    CACHE_TTL_SECONDS,
    CACHE_MAX_FILES,
    DEFAULT_CONTEXT_WINDOW,
    CONTEXT_RESERVE_PERCENT,
)

__all__ = [
    'RAGEngine',
    'MarkdownChunker',
    'QueryCache',
    'ContextOptimizer',
    'SimpleBM25',
    'ChunkMetadata',
    'TOKENS_PER_CHAR',
    'MIN_CHUNK_TOKENS',
    'DEFAULT_CHUNK_TOKENS',
    'CACHE_TTL_SECONDS',
    'CACHE_MAX_FILES',
    'DEFAULT_CONTEXT_WINDOW',
    'CONTEXT_RESERVE_PERCENT',
]
