"""Query result caching with TTL and file tracking."""

import os
import time
from typing import List, Optional, Dict
from collections import OrderedDict


# Cache settings
CACHE_TTL_SECONDS = 600  # 10 minutes
CACHE_MAX_FILES = 5


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
