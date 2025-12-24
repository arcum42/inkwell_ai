import os
import re
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Tuple, Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict
import time
import math

# Token estimation: approximately 1 token per 4 characters for English text
TOKENS_PER_CHAR = 0.25
MIN_CHUNK_TOKENS = 50  # Lowered to capture smaller sections
DEFAULT_CHUNK_TOKENS = 500
MAX_CHUNK_TOKENS = 1500
CHUNK_OVERLAP_TOKENS = 50

# Cache settings
CACHE_TTL_SECONDS = 600  # 10 minutes
CACHE_MAX_FILES = 5

# Hybrid search weights
KEYWORD_WEIGHT = 0.4
SEMANTIC_WEIGHT = 0.6
MIN_HYBRID_RESULTS = 3  # Minimum results guaranteed

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

class SimpleBM25:
    """Simple BM25 implementation for keyword-based ranking."""
    
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1  # Term frequency saturation parameter
        self.b = b    # Length normalization parameter
        self.documents = []  # List of tokenized documents
        self.idf = {}  # Inverse document frequency cache
        self.avg_doc_length = 0
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase, split on whitespace, remove short tokens."""
        tokens = text.lower().split()
        # Filter out very short tokens and common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'is', 'in', 'to', 'of', 'for', 'on', 'with', 'at', 'by'}
        return [t for t in tokens if len(t) > 2 and t not in stop_words]
    
    def index(self, documents: List[str]):
        """Index a list of documents."""
        self.documents = [self._tokenize(doc) for doc in documents]
        self.avg_doc_length = sum(len(doc) for doc in self.documents) / len(self.documents) if self.documents else 0
        
        # Calculate IDF for all terms
        doc_frequencies = {}
        for doc in self.documents:
            for term in set(doc):
                doc_frequencies[term] = doc_frequencies.get(term, 0) + 1
        
        total_docs = len(self.documents)
        for term, freq in doc_frequencies.items():
            self.idf[term] = math.log((total_docs - freq + 0.5) / (freq + 0.5) + 1)
    
    def score(self, query: str) -> List[float]:
        """Score all documents for a query. Returns list of scores."""
        query_tokens = self._tokenize(query)
        scores = []
        
        for doc in self.documents:
            score = 0
            for token in query_tokens:
                if token in self.idf:
                    # Count occurrences in document
                    term_freq = doc.count(token)
                    if term_freq > 0:
                        idf = self.idf[token]
                        # BM25 formula
                        numerator = idf * term_freq * (self.k1 + 1)
                        denominator = term_freq + self.k1 * (1 - self.b + self.b * len(doc) / max(self.avg_doc_length, 1))
                        score += numerator / denominator
            scores.append(score)
        
        return scores

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
            # Always include the final chunk, even if smaller than min_tokens
            # This ensures small documents and tail sections aren't lost
            if chunk_text:
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
        
        # Initialize BM25 indexer for hybrid search
        self.bm25 = SimpleBM25()
        self._all_chunks = []  # Keep track of all indexed chunks for BM25

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
        
        # Update BM25 index with all documents
        all_docs = self.collection.get()
        if all_docs['documents']:
            self._all_chunks = list(zip(all_docs['ids'], all_docs['documents']))
            self.bm25.index(all_docs['documents'])
        
        # Invalidate cache for this file (unless bulk indexing)
        if invalidate_cache:
            self.query_cache.invalidate_file(file_path)
        
        # Track indexed file with modification time
        try:
            self._indexed_files[file_path] = os.path.getmtime(file_path)
        except Exception:
            pass
        
        print(f"[RAG] Indexed {len(chunks)} chunks for {file_path}")

    def query(self, query_text, n_results=3, debug=False, use_hybrid=True):
        """Retrieves relevant chunks with optional hybrid search (BM25 + semantic)."""
        # Try cache first
        cached_results = self.query_cache.get(query_text)
        if cached_results is not None:
            if debug:
                stats = self.query_cache.get_stats()
                print(f"[RAG Cache] HIT - Query: '{query_text[:50]}...' | Stats: {stats}")
            return cached_results
        
        # If hybrid search is disabled or BM25 not ready, use semantic search only
        if not use_hybrid or not self._all_chunks:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            result_docs = results['documents'][0] if results['documents'] else []
            result_sources = [meta.get('source', 'unknown') for meta in results['metadatas'][0]] if results['metadatas'] else []
            self.query_cache.set(query_text, result_docs, result_sources)
            
            if debug:
                stats = self.query_cache.get_stats()
                print(f"[RAG Cache] MISS (semantic-only) - Query: '{query_text[:50]}...' | Sources: {result_sources} | Stats: {stats}")
            
            return result_docs
        
        # HYBRID SEARCH: Combine BM25 keyword search with semantic embeddings
        
        # 1. Get semantic results from Chroma
        semantic_results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results * 2  # Get more results to re-rank
        )
        
        semantic_docs = semantic_results['documents'][0] if semantic_results['documents'] else []
        semantic_ids = semantic_results['ids'][0] if semantic_results['ids'] else []
        semantic_distances = semantic_results['distances'][0] if semantic_results['distances'] else []
        
        # Convert distances to similarity scores (1 - distance)
        semantic_scores = {doc_id: 1 - (distance / 2) for doc_id, distance in zip(semantic_ids, semantic_distances)}
        
        # Normalize semantic scores to 0-1
        max_semantic = max(semantic_scores.values()) if semantic_scores else 1
        if max_semantic > 0:
            semantic_scores = {k: v / max_semantic for k, v in semantic_scores.items()}
        
        # 2. Get BM25 keyword scores
        bm25_scores_all = self.bm25.score(query_text)
        bm25_scores = {}
        for chunk_id, bm25_score in zip([cid for cid, _ in self._all_chunks], bm25_scores_all):
            bm25_scores[chunk_id] = bm25_score
        
        # Normalize BM25 scores to 0-1
        max_bm25 = max(bm25_scores.values()) if bm25_scores else 1
        if max_bm25 > 0:
            bm25_scores = {k: v / max_bm25 for k, v in bm25_scores.items()}
        
        # 3. Combine scores: hybrid_score = (keyword_weight * bm25 + semantic_weight * semantic)
        hybrid_scores = {}
        all_ids = set(semantic_scores.keys()) | set(bm25_scores.keys())
        
        for doc_id in all_ids:
            semantic_score = semantic_scores.get(doc_id, 0)
            bm25_score = bm25_scores.get(doc_id, 0)
            hybrid_scores[doc_id] = (KEYWORD_WEIGHT * bm25_score) + (SEMANTIC_WEIGHT * semantic_score)
        
        # 4. Rank by hybrid score
        sorted_results = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 5. Apply fallback strategy: ensure minimum results
        selected_ids = [doc_id for doc_id, _ in sorted_results[:n_results]]
        
        # If we have too few results, add more from BM25 or semantic scores
        if len(selected_ids) < MIN_HYBRID_RESULTS:
            remaining_ids = [doc_id for doc_id, _ in sorted_results[n_results:]]
            selected_ids.extend(remaining_ids[:MIN_HYBRID_RESULTS - len(selected_ids)])
        
        # 6. Build final result list in score order
        result_docs = []
        result_sources = []
        result_scores = []
        
        for chunk_id in selected_ids:
            # Find the document text and metadata
            for stored_id, stored_doc in self._all_chunks:
                if stored_id == chunk_id:
                    result_docs.append(stored_doc)
                    score = hybrid_scores.get(chunk_id, 0)
                    result_scores.append(score)
                    # Get source from metadata
                    meta = self.collection.get(ids=[chunk_id])
                    if meta['metadatas']:
                        source = meta['metadatas'][0].get('source', 'unknown')
                        result_sources.append(source)
                    break
        
        # Store in cache
        self.query_cache.set(query_text, result_docs, result_sources)
        
        if debug:
            stats = self.query_cache.get_stats()
            method_breakdown = f"BM25={KEYWORD_WEIGHT*100:.0f}% + Semantic={SEMANTIC_WEIGHT*100:.0f}%"
            print(f"[RAG Cache] MISS (hybrid) - Query: '{query_text[:50]}...' | {method_breakdown}")
            print(f"  Sources: {result_sources}")
            print(f"  Hybrid Scores: {[f'{s:.2f}' for s in result_scores]}")
            print(f"  Cache Stats: {stats}")
        
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

