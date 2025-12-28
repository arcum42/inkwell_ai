"""Main RAG engine orchestrating search and retrieval."""

import os
import time
import chromadb
from typing import List, Tuple, Optional, Dict

from .metadata import ChunkMetadata
from .cache import QueryCache, CACHE_TTL_SECONDS, CACHE_MAX_FILES
from .chunking import MarkdownChunker
from .search import SimpleBM25
from .context import ContextOptimizer, DEFAULT_CONTEXT_WINDOW, CONTEXT_RESERVE_PERCENT


# Hybrid search weights
KEYWORD_WEIGHT = 0.4
SEMANTIC_WEIGHT = 0.6
MIN_HYBRID_RESULTS = 3
FILE_RECENCY_WEIGHT = 0.15

# Recency decay windows (seconds)
RECENCY_FULL_SECONDS = 6 * 3600
RECENCY_ZERO_SECONDS = 30 * 24 * 3600

# Directories to exclude from indexing and querying
EXCLUDED_DIRS = {".inkwell_rag", ".debug", ".git", "node_modules", "__pycache__", "venv", ".venv"}


class RAGEngine:
    def __init__(self, project_path):
        self.project_path = project_path
        self.db_path = os.path.join(project_path, ".inkwell_rag")
        
        # Initialize Client
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Create or get collection
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
        
        # Initialize context optimizer for token-aware truncation
        self.context_optimizer = ContextOptimizer(
            context_window=DEFAULT_CONTEXT_WINDOW,
            reserve_percent=CONTEXT_RESERVE_PERCENT
        )
        
        # Track recency for context prioritization
        self._file_access_times = {}  # source -> timestamp of last query result inclusion

    def _should_exclude_file(self, file_path: str) -> bool:
        """Check if a file path should be excluded from RAG.
        
        Args:
            file_path: Absolute or relative file path to check
            
        Returns:
            True if file should be excluded (e.g., in .debug folder)
        """
        # Normalize path separators
        normalized_path = file_path.replace('\\', '/')
        
        # Check if any excluded directory appears in the path
        path_parts = normalized_path.split('/')
        for part in path_parts:
            if part in EXCLUDED_DIRS:
                return True
        
        return False
    
    def _get_file_recency_score(self, file_path: str, current_time: Optional[float] = None) -> float:
        """Return a 0-1 freshness score based on file modification time."""
        if current_time is None:
            current_time = time.time()

        mtime = self._indexed_files.get(file_path)
        if mtime is None:
            try:
                mtime = os.path.getmtime(file_path)
            except OSError:
                return 0.0

        age_seconds = current_time - mtime

        if age_seconds <= RECENCY_FULL_SECONDS:
            return 1.0
        if age_seconds >= RECENCY_ZERO_SECONDS:
            return 0.0

        decay_span = RECENCY_ZERO_SECONDS - RECENCY_FULL_SECONDS
        return max(0.0, 1.0 - (age_seconds - RECENCY_FULL_SECONDS) / decay_span)
    
    def set_context_window(self, context_window: int):
        """Set the model's context window size for optimization.
        
        Args:
            context_window: Total tokens available in model context
        """
        self.context_optimizer.set_context_window(context_window)
    
    def _calculate_recency_bonus(self) -> Dict[str, float]:
        """Calculate recency bonus for each source file.
        
        Returns: Dictionary mapping source file to recency score (0-1)
        """
        if not self._file_access_times:
            return {}
        
        current_time = time.time()
        recency_bonus = {}
        
        for source, access_time in self._file_access_times.items():
            # Time decay: files accessed < 1 minute ago get full bonus
            # Files accessed 1 hour ago get 0 bonus
            time_diff = current_time - access_time
            one_hour = 3600
            
            if time_diff <= 60:
                bonus = 1.0
            elif time_diff >= one_hour:
                bonus = 0.0
            else:
                # Linear decay between 1 minute and 1 hour
                bonus = 1.0 - (time_diff - 60) / (one_hour - 60)
            
            recency_bonus[source] = max(0, min(1, bonus))
        
        return recency_bonus

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

    def query(self, query_text, n_results=3, debug=False, use_hybrid=True, include_metadata=False):
        """Retrieves relevant chunks with optional hybrid search (BM25 + semantic).

        Args:
            query_text: Query text
            n_results: Number of chunks to return
            debug: Print debug info
            use_hybrid: Use BM25 + semantic hybrid search when True
            include_metadata: Return list of {text, metadata} when True
        """
        use_cache = not include_metadata

        # Try cache first (only when metadata is not requested)
        if use_cache:
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
                n_results=n_results * 2  # Get more to account for filtering
            )
            result_docs_raw = results['documents'][0] if results['documents'] else []
            result_metas_raw = results['metadatas'][0] if results['metadatas'] else []
            
            # Filter out excluded directories (e.g., .debug)
            result_docs = []
            result_metas = []
            for doc, meta in zip(result_docs_raw, result_metas_raw):
                source = meta.get('source', 'unknown')
                if not self._should_exclude_file(source):
                    result_docs.append(doc)
                    result_metas.append(meta)
                    if len(result_docs) >= n_results:
                        break
            
            result_sources = [meta.get('source', 'unknown') for meta in result_metas]

            if include_metadata:
                entries = []
                distances = results['distances'][0] if results['distances'] else []
                for doc, meta, distance in zip(result_docs, result_metas, distances):
                    score = 1 - (distance / 2) if distance is not None else 0
                    meta_copy = dict(meta)
                    meta_copy['score'] = score
                    entries.append({"text": doc, "metadata": meta_copy})
                if debug:
                    print(f"[RAG] Semantic-only results with metadata: {len(entries)} chunks")
                return entries

            if use_cache:
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
        #    then blend with file recency freshness
        hybrid_scores = {}
        all_ids = set(semantic_scores.keys()) | set(bm25_scores.keys())
        current_time = time.time()
        
        for doc_id in all_ids:
            semantic_score = semantic_scores.get(doc_id, 0)
            bm25_score = bm25_scores.get(doc_id, 0)
            base_score = (KEYWORD_WEIGHT * bm25_score) + (SEMANTIC_WEIGHT * semantic_score)

            # Boost fresher files using modification times
            source_path = doc_id.split("#", 1)[0]
            recency_score = self._get_file_recency_score(source_path, current_time)

            hybrid_scores[doc_id] = ((1 - FILE_RECENCY_WEIGHT) * base_score) + (FILE_RECENCY_WEIGHT * recency_score)
        
        # 4. Rank by hybrid score
        sorted_results = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 5. Apply fallback strategy: ensure minimum results
        selected_ids = [doc_id for doc_id, _ in sorted_results[:n_results]]
        
        # If we have too few results, add more from BM25 or semantic scores
        if len(selected_ids) < MIN_HYBRID_RESULTS:
            remaining_ids = [doc_id for doc_id, _ in sorted_results[n_results:]]
            selected_ids.extend(remaining_ids[:MIN_HYBRID_RESULTS - len(selected_ids)])
        
        # 6. Build final result list in score order, filtering excluded directories
        result_docs = []
        result_sources = []
        result_scores = []
        
        for chunk_id in selected_ids:
            # Find the document text and metadata
            for stored_id, stored_doc in self._all_chunks:
                if stored_id == chunk_id:
                    # Get source from metadata
                    meta = self.collection.get(ids=[chunk_id])
                    if meta['metadatas']:
                        source = meta['metadatas'][0].get('source', 'unknown')
                        
                        # Skip excluded files (e.g., .debug)
                        if self._should_exclude_file(source):
                            break
                        
                        result_docs.append(stored_doc)
                        score = hybrid_scores.get(chunk_id, 0)
                        result_scores.append(score)
                        result_sources.append(source)
                    break
        
        # Store in cache when allowed
        if use_cache:
            self.query_cache.set(query_text, result_docs, result_sources)
        
        if include_metadata:
            entries = []
            for chunk_id, chunk_text in zip(selected_ids, result_docs):
                meta = self.collection.get(ids=[chunk_id])
                meta_dict = meta['metadatas'][0] if meta['metadatas'] else {}
                meta_copy = dict(meta_dict)
                meta_copy['score'] = hybrid_scores.get(chunk_id, 0)
                entries.append({"text": chunk_text, "metadata": meta_copy})
            if debug:
                stats = self.query_cache.get_stats()
                method_breakdown = (
                    f"BM25={KEYWORD_WEIGHT*100:.0f}% + Semantic={SEMANTIC_WEIGHT*100:.0f}% "
                    f"+ Recency={FILE_RECENCY_WEIGHT*100:.0f}%"
                )
                print(f"[RAG Cache] MISS (hybrid) - Query: '{query_text[:50]}...' | {method_breakdown}")
                print(f"  Sources: {result_sources}")
                print(f"  Hybrid Scores: {[f'{s:.2f}' for s in result_scores]}")
                print(f"  Cache Stats: {stats}")
            return entries

        if debug:
            stats = self.query_cache.get_stats()
            method_breakdown = (
                f"BM25={KEYWORD_WEIGHT*100:.0f}% + Semantic={SEMANTIC_WEIGHT*100:.0f}% "
                f"+ Recency={FILE_RECENCY_WEIGHT*100:.0f}%"
            )
            print(f"[RAG Cache] MISS (hybrid) - Query: '{query_text[:50]}...' | {method_breakdown}")
            print(f"  Sources: {result_sources}")
            print(f"  Hybrid Scores: {[f'{s:.2f}' for s in result_scores]}")
            print(f"  Cache Stats: {stats}")
        
        return result_docs

    def get_optimized_context(self, query_text: str, n_results: int = 5,
                              context_window: Optional[int] = None,
                              debug: bool = False) -> Tuple[List[str], Dict]:
        """Get RAG context optimized to fit within model's context window.

        Performs RAG query and intelligently truncates results to fit within
        a percentage of the model's context window, preserving the most relevant chunks.

        Args:
            query_text: Query to search for
            n_results: Number of results to retrieve (before truncation)
            context_window: Override context window size (uses stored value if None)
            debug: Print debug information

        Returns:
            Tuple of (optimized_chunks, optimization_stats)
        """
        # Update context window if provided
        if context_window:
            self.set_context_window(context_window)

        # Get raw query results (get extra for re-ranking)
        raw_results = self.query(query_text, n_results=n_results, debug=debug, use_hybrid=True)

        if not raw_results:
            return [], {"status": "no_results", "total_tokens": 0, "used_tokens": 0}

        # Get metadata for results
        chunks_with_meta = []
        for chunk_text in raw_results:
            # Try to find metadata from collection
            meta = self.collection.get(
                where={"$contains": chunk_text[:100]},  # Rough matching
            )
            if meta['metadatas']:
                metadata = meta['metadatas'][0]
            else:
                metadata = {"source": "unknown", "heading_path": []}

            chunks_with_meta.append((chunk_text, metadata))

        # Get recency bonuses
        recency_bonus = self._calculate_recency_bonus()

        # Calculate semantic scores from result order (first result highest)
        semantic_scores = [max(0, 1.0 - (i * 0.2)) for i in range(len(chunks_with_meta))]

        # Optimize context
        optimized_chunks, stats = self.context_optimizer.optimize_context(
            chunks_with_meta,
            query=query_text,
            semantic_scores=semantic_scores,
            recency_bonus=recency_bonus,
            debug=debug
        )

        # Update recency tracking for included chunks
        current_time = time.time()
        for chunk_text, metadata in optimized_chunks:
            source = metadata.get('source', 'unknown')
            self._file_access_times[source] = current_time

        # Extract just the text from optimized chunks
        optimized_text = [text for text, _ in optimized_chunks]

        return optimized_text, stats

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
    
    def clean_excluded_files(self):
        """Remove all chunks from excluded directories (e.g., .debug) from the database.
        
        This should be called periodically or after adding new exclusions to clean up
        any previously-indexed files from blacklisted directories.
        """
        print("[RAG] Cleaning excluded files from database...")
        
        # Get all document IDs from collection
        all_docs = self.collection.get()
        if not all_docs['ids']:
            print("[RAG] No documents in collection to clean.")
            return
        
        excluded_ids = []
        for doc_id, metadata in zip(all_docs['ids'], all_docs['metadatas']):
            source = metadata.get('source', '')
            if self._should_exclude_file(source):
                excluded_ids.append(doc_id)
                print(f"[RAG] Marking for removal: {source}")
        
        if excluded_ids:
            print(f"[RAG] Removing {len(excluded_ids)} chunks from excluded directories...")
            self.collection.delete(ids=excluded_ids)
            
            # Also remove from BM25 index and chunk tracking
            self._all_chunks = [(cid, doc) for cid, doc in self._all_chunks if cid not in excluded_ids]
            if self._all_chunks:
                self.bm25.index([doc for _, doc in self._all_chunks])
            
            # Clear cache since index changed
            self.query_cache.invalidate_all()
            
            print(f"[RAG] Removed {len(excluded_ids)} chunks from excluded directories.")
        else:
            print("[RAG] No excluded files found in database.")
    
    def remove_file(self, file_path: str):
        """Remove all chunks for a specific file from the index.
        
        Args:
            file_path: Path to the file to remove from index
        """
        # Find all chunk IDs for this file
        all_docs = self.collection.get()
        if not all_docs['ids']:
            return
        
        file_ids = []
        for doc_id, metadata in zip(all_docs['ids'], all_docs['metadatas']):
            if metadata.get('source') == file_path:
                file_ids.append(doc_id)
        
        if file_ids:
            self.collection.delete(ids=file_ids)
            # Also remove from BM25 index and chunk tracking
            self._all_chunks = [(cid, doc) for cid, doc in self._all_chunks if cid not in file_ids]
            if self._all_chunks:
                self.bm25.index([doc for _, doc in self._all_chunks])
            # Remove from indexed files tracking
            if file_path in self._indexed_files:
                del self._indexed_files[file_path]
            # Clear cache since index changed
            self.query_cache.invalidate_file(file_path)
            print(f"[RAG] Removed {len(file_ids)} chunks for {file_path}")
    
    def index_project(self):
        """Walks the project and indexes all markdown files."""
        # Invalidate entire cache for bulk reindexing
        self.query_cache.invalidate_all()
        
        excluded_dirs = EXCLUDED_DIRS

        for root, dirs, files in os.walk(self.project_path):
            # Prune excluded directories to avoid descending into them
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            if any(excluded in root for excluded in excluded_dirs):
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
