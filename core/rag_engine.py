import os
import re
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Tuple, Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict
import time

# Token estimation: approximately 1 token per 4 characters for English text
TOKENS_PER_CHAR = 0.25
MIN_CHUNK_TOKENS = 50  # Lowered to capture smaller sections
DEFAULT_CHUNK_TOKENS = 500
MAX_CHUNK_TOKENS = 1500
CHUNK_OVERLAP_TOKENS = 50

# Cache settings
CACHE_TTL_SECONDS = 600  # 10 minutes
CACHE_MAX_FILES = 5

class ChunkMetadata:
    """Metadata for a chunk with heading hierarchy and location info."""
    def __init__(self, source: str, heading_path: List[str], start_line: int, end_line: int, 
                 content_type: str = "text", chunk_index: int = 0):
        self.source = source
        self.heading_path = heading_path  # e.g., ["Chapter 1", "Section A", "Subsection"]
        self.start_line = start_line
        self.end_line = end_line
        self.content_type = content_type  # "text", "code", "frontmatter", "heading"
        self.chunk_index = chunk_index
    
    def to_dict(self):
        return {
            "source": self.source,
            "heading_path": " > ".join(self.heading_path) if self.heading_path else "Root",
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_type": self.content_type,
            "chunk_index": self.chunk_index
        }

class QueryCache:
    """Cache for RAG query results with TTL and file tracking."""
    
    def __init__(self, ttl_seconds=CACHE_TTL_SECONDS, max_files=CACHE_MAX_FILES):
        self.ttl_seconds = ttl_seconds
        self.max_files = max_files
        self.cache = OrderedDict()  # {query_text: (results, timestamp, file_paths_used)}
        self.file_timestamps = {}   # {file_path: last_mtime}
        self.stats = {"hits": 0, "misses": 0, "invalidations": 0}
    
    def get(self, query_text: str, file_paths_context: List[str] = None) -> Optional[List[str]]:
        """Retrieve cached results if valid. Returns None if expired or invalidated."""
        if query_text not in self.cache:
            self.stats["misses"] += 1
            return None
        
        results, timestamp, cached_files = self.cache[query_text]
        
        # Check TTL
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[query_text]
            self.stats["invalidations"] += 1
            self.stats["misses"] += 1
            return None
        
        # Check if any cached files have been modified
        for file_path in cached_files:
            if not os.path.exists(file_path):
                # File was deleted, invalidate cache
                del self.cache[query_text]
                self.stats["invalidations"] += 1
                self.stats["misses"] += 1
                return None
            
            try:
                current_mtime = os.path.getmtime(file_path)
                if file_path not in self.file_timestamps:
                    # First time seeing this file, store its mtime
                    self.file_timestamps[file_path] = current_mtime
                elif current_mtime > self.file_timestamps[file_path]:
                    # File has been modified since cache entry
                    del self.cache[query_text]
                    self.stats["invalidations"] += 1
                    self.stats["misses"] += 1
                    return None
            except OSError:
                # Can't access file, invalidate cache
                del self.cache[query_text]
                self.stats["invalidations"] += 1
                self.stats["misses"] += 1
                return None
        
        # Cache hit
        self.stats["hits"] += 1
        return results
    
    def set(self, query_text: str, results: List[str], file_paths_used: List[str] = None):
        """Store query results in cache."""
        if file_paths_used is None:
            file_paths_used = []
        
        # Update file timestamps for files that exist
        for file_path in file_paths_used:
            if os.path.exists(file_path):
                try:
                    self.file_timestamps[file_path] = os.path.getmtime(file_path)
                except (OSError, FileNotFoundError):
                    pass
        
        # Enforce cache size limit
        if len(self.cache) >= self.max_files:
            # Remove oldest entry (FIFO)
            self.cache.popitem(last=False)
        
        self.cache[query_text] = (results, time.time(), file_paths_used)
    
    def invalidate_file(self, file_path: str):
        """Invalidate all cache entries that used this file."""
        invalidated_count = 0
        queries_to_remove = [
            query for query, (_, _, files) in self.cache.items()
            if file_path in files
        ]
        for query in queries_to_remove:
            del self.cache[query]
            invalidated_count += 1
        
        if invalidated_count > 0:
            self.stats["invalidations"] += invalidated_count
            print(f"[RAG Cache] Invalidated {invalidated_count} cache entries for {file_path}")
    
    def invalidate_all(self):
        """Clear all cache entries."""
        count = len(self.cache)
        self.cache.clear()
        self.file_timestamps.clear()
        if count > 0:
            self.stats["invalidations"] += count
            print(f"[RAG Cache] Cleared all {count} cache entries")
    
    def get_stats(self) -> Dict:
        """Return cache statistics."""
        total_queries = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_queries * 100) if total_queries > 0 else 0
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "invalidations": self.stats["invalidations"],
            "hit_rate": f"{hit_rate:.1f}%",
            "cached_queries": len(self.cache)
        }

class MarkdownChunker:
    """Intelligent chunker for Markdown documents."""
    
    def __init__(self, min_tokens=MIN_CHUNK_TOKENS, default_tokens=DEFAULT_CHUNK_TOKENS, 
                 max_tokens=MAX_CHUNK_TOKENS, overlap_tokens=CHUNK_OVERLAP_TOKENS):
        self.min_tokens = min_tokens
        self.default_tokens = default_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return max(1, int(len(text) * TOKENS_PER_CHAR))
    
    def _extract_frontmatter(self, text: str) -> Tuple[Optional[str], str]:
        """Extract YAML/TOML frontmatter if present. Returns (frontmatter, remaining_text)."""
        if text.startswith('---'):
            match = re.match(r'^---\n(.*?)\n---\n(.*)', text, re.DOTALL)
            if match:
                return match.group(1), match.group(2)
        elif text.startswith('+++'):
            match = re.match(r'^\+\+\+\n(.*?)\n\+\+\+\n(.*)', text, re.DOTALL)
            if match:
                return match.group(1), match.group(2)
        return None, text
    
    def _is_heading(self, line: str) -> Tuple[bool, int, str]:
        """Check if line is a heading. Returns (is_heading, level, text)."""
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            return True, level, text
        return False, 0, ""
    
    def _is_code_fence(self, line: str) -> Tuple[bool, str]:
        """Check if line starts a code fence. Returns (is_fence, language)."""
        match = re.match(r'^```(\w*)', line)
        if match:
            return True, match.group(1) or "text"
        return False, ""
    
    def chunk(self, text: str, file_path: str) -> List[Tuple[str, ChunkMetadata]]:
        """
        Intelligently chunk Markdown text respecting structure.
        Returns list of (chunk_text, metadata) tuples.
        """
        chunks = []
        frontmatter, text = self._extract_frontmatter(text)
        
        # Add frontmatter as its own chunk if present
        if frontmatter:
            metadata = ChunkMetadata(
                source=file_path,
                heading_path=["Frontmatter"],
                start_line=1,
                end_line=frontmatter.count('\n'),
                content_type="frontmatter",
                chunk_index=0
            )
            chunks.append((frontmatter, metadata))
        
        lines = text.split('\n')
        current_chunk = []
        current_tokens = 0
        heading_stack = []  # Stack to track heading hierarchy: list of (level, text)
        chunk_start_line = 0
        chunk_index = 1 if frontmatter else 0
        in_code_block = False
        
        for line_idx, line in enumerate(lines):
            is_heading, level, heading_text = self._is_heading(line)
            is_fence, language = self._is_code_fence(line)
            
            # Track code blocks
            if is_fence:
                in_code_block = not in_code_block
            
            line_tokens = self.estimate_tokens(line)
            
            # Decide whether to flush chunk BEFORE updating heading stack
            should_flush = False
            
            if is_heading and len(current_chunk) > 0:
                # Always flush before a new heading (except the very first)
                should_flush = True
            elif current_tokens + line_tokens > self.max_tokens:
                # Flush if adding this line exceeds max tokens
                should_flush = True
            elif in_code_block and current_tokens + line_tokens > self.default_tokens * 2:
                # Code blocks can be larger, but cap at 2x default
                should_flush = current_tokens > self.default_tokens
            
            # Flush current chunk if needed
            if should_flush and len(current_chunk) > 0:
                chunk_text = '\n'.join(current_chunk).strip()
                if self.estimate_tokens(chunk_text) >= self.min_tokens:
                    # Use heading stack at time of flush
                    metadata = ChunkMetadata(
                        source=file_path,
                        heading_path=[h[1] for h in heading_stack],
                        start_line=chunk_start_line,
                        end_line=line_idx,
                        content_type="code" if in_code_block else "text",
                        chunk_index=chunk_index
                    )
                    chunks.append((chunk_text, metadata))
                    chunk_index += 1
                
                # Start new chunk with overlap
                overlap_lines = []
                overlap_tokens = 0
                for prev_line in reversed(current_chunk):
                    prev_tokens = self.estimate_tokens(prev_line)
                    if overlap_tokens + prev_tokens <= self.overlap_tokens:
                        overlap_lines.insert(0, prev_line)
                        overlap_tokens += prev_tokens
                    else:
                        break
                
                current_chunk = overlap_lines
                current_tokens = overlap_tokens
                chunk_start_line = line_idx
            
            # NOW update heading stack for next iteration
            if is_heading:
                # Remove headings of equal or greater level from stack
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading_text))
            
            # Add line to current chunk
            current_chunk.append(line)
            current_tokens += line_tokens
        
        # Flush remaining chunk
        if len(current_chunk) > 0:
            chunk_text = '\n'.join(current_chunk).strip()
            if self.estimate_tokens(chunk_text) >= self.min_tokens:
                metadata = ChunkMetadata(
                    source=file_path,
                    heading_path=[h[1] for h in heading_stack],
                    start_line=chunk_start_line,
                    end_line=len(lines),
                    content_type="code" if in_code_block else "text",
                    chunk_index=chunk_index
                )
                chunks.append((chunk_text, metadata))
        
        return chunks

class RAGEngine:
    def __init__(self, project_path):
        self.project_path = project_path
        self.db_path = os.path.join(project_path, ".inkwell_rag")
        
        # Initialize Client
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Create or get collection
        # We use the default embedding function (all-MiniLM-L6-v2)
        self.collection = self.client.get_or_create_collection(name="project_docs")
        
        # Cache of indexed file mtimes for status tracking
        self._indexed_files = {}  # path -> mtime
        
        # Initialize chunker
        self.chunker = MarkdownChunker()
        
        # Initialize query cache
        self.query_cache = QueryCache(ttl_seconds=CACHE_TTL_SECONDS, max_files=CACHE_MAX_FILES)

    def index_file(self, file_path, content, invalidate_cache=True):
        """Indexes a single file using Markdown-aware chunking."""
        if not content:
            return

        # Use intelligent chunking
        chunks = self.chunker.chunk(content, file_path)
        
        if not chunks:
            return

        # Prepare data for upsert
        documents = []
        ids = []
        metadatas = []
        
        for chunk_text, chunk_meta in chunks:
            documents.append(chunk_text)
            ids.append(f"{file_path}#{chunk_meta.chunk_index}")
            metadatas.append(chunk_meta.to_dict())
        
        # Upsert (overwrite if exists)
        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        # Invalidate cache for this file (unless bulk indexing)
        if invalidate_cache:
            self.query_cache.invalidate_file(file_path)
        
        # Track indexed file with modification time
        try:
            self._indexed_files[file_path] = os.path.getmtime(file_path)
        except Exception:
            pass
        
        print(f"[RAG] Indexed {len(chunks)} chunks for {file_path}")

    def query(self, query_text, n_results=3, debug=False):
        """Retrieves relevant chunks for the query with caching."""
        # Try cache first
        cached_results = self.query_cache.get(query_text)
        if cached_results is not None:
            if debug:
                stats = self.query_cache.get_stats()
                print(f"[RAG Cache] HIT - Query: '{query_text[:50]}...' | Stats: {stats}")
            return cached_results
        
        # Cache miss - query the collection
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        # Extract results
        result_docs = results['documents'][0] if results['documents'] else []
        result_sources = [meta.get('source', 'unknown') for meta in results['metadatas'][0]] if results['metadatas'] else []
        
        # Store in cache with file sources
        self.query_cache.set(query_text, result_docs, result_sources)
        
        if debug:
            stats = self.query_cache.get_stats()
            print(f"[RAG Cache] MISS - Query: '{query_text[:50]}...' | Sources: {result_sources} | Stats: {stats}")
        
        return result_docs

    def get_file_index_status(self, file_path):
        """Get index status for a file.
        Returns: 'indexed', 'needs_reindex', 'not_indexed'
        """
        if not file_path.endswith(('.md', '.txt')):
            return None
        
        if file_path not in self._indexed_files:
            return 'not_indexed'
        
        try:
            current_mtime = os.path.getmtime(file_path)
            indexed_mtime = self._indexed_files[file_path]
            if current_mtime > indexed_mtime:
                return 'needs_reindex'
            return 'indexed'
        except Exception:
            return 'not_indexed'
    
    def index_project(self):
        """Walks the project and indexes all markdown files."""
        # Invalidate entire cache for bulk reindexing
        self.query_cache.invalidate_all()
        
        for root, dirs, files in os.walk(self.project_path):
            if ".inkwell_rag" in root:
                continue
            for file in files:
                if file.endswith((".md", ".txt")):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        # Don't invalidate cache individually during bulk indexing
                        self.index_file(path, content, invalidate_cache=False)
                    except Exception as e:
                        print(f"[RAG] Error indexing {path}: {e}")

