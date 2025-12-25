"""RAG (Retrieval Augmented Generation) module for semantic search and context retrieval.

This module provides intelligent document chunking, hybrid search (keyword + semantic),
and context-aware optimization for fitting RAG results into model context windows.

Main classes:
    RAGEngine: Main orchestrator for indexing and querying documents
    MarkdownChunker: Intelligent chunking of markdown documents
    QueryCache: Caching layer with TTL and file modification tracking
    ContextOptimizer: Optimizes context to fit within token limits
    SimpleBM25: Keyword-based search using BM25 algorithm
    ChunkMetadata: Metadata storage for chunks
"""

from .engine import RAGEngine
from .chunking import MarkdownChunker, TOKENS_PER_CHAR, MIN_CHUNK_TOKENS, DEFAULT_CHUNK_TOKENS
from .cache import QueryCache, CACHE_TTL_SECONDS, CACHE_MAX_FILES
from .context import ContextOptimizer, DEFAULT_CONTEXT_WINDOW, CONTEXT_RESERVE_PERCENT
from .search import SimpleBM25
from .metadata import ChunkMetadata

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
