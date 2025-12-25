"""Context optimization for fitting RAG results into model's context window."""

import time
from typing import List, Tuple, Optional, Dict


# Token estimation settings
TOKENS_PER_CHAR = 0.25

# Context window settings
DEFAULT_CONTEXT_WINDOW = 4096
CONTEXT_RESERVE_PERCENT = 0.70
MIN_CONTEXT_TOKENS = 500


class ContextOptimizer:
    """Optimizes RAG context to fit within model's context window."""
    
    def __init__(self, context_window=DEFAULT_CONTEXT_WINDOW, reserve_percent=CONTEXT_RESERVE_PERCENT):
        """Initialize context optimizer.
        
        Args:
            context_window: Total tokens available in model's context
            reserve_percent: Maximum % of context to use for RAG (rest for response)
        """
        self.context_window = context_window
        self.reserve_percent = reserve_percent
        self.max_rag_tokens = int(context_window * reserve_percent)
        self.min_response_tokens = int(context_window * (1 - reserve_percent))
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return max(1, int(len(text) * TOKENS_PER_CHAR))
    
    def optimize_context(self, chunks: List[Tuple[str, Dict]], 
                         query: Optional[str] = None,
                         semantic_scores: Optional[List[float]] = None,
                         recency_bonus: Optional[Dict[str, float]] = None,
                         debug: bool = False) -> Tuple[List[Tuple[str, Dict]], Dict]:
        """Optimize chunks to fit within context window.
        
        Args:
            chunks: List of (text, metadata_dict) tuples from RAG query
            query: Original query for context (optional)
            semantic_scores: Semantic relevance scores (0-1) for each chunk
            recency_bonus: Dictionary mapping source file to recency score (0-1)
            debug: Print debug information
            
        Returns:
            Tuple of (optimized_chunks, optimization_stats)
        """
        if not chunks:
            return [], {"status": "no_chunks", "total_tokens": 0, "used_tokens": 0}
        
        # Calculate priority scores for each chunk
        chunk_scores = []
        total_tokens = 0
        
        for i, (chunk_text, metadata) in enumerate(chunks):
            tokens = self.estimate_tokens(chunk_text)
            total_tokens += tokens
            
            # Build composite score: semantic_score + recency_bonus
            score = 0.5  # Base score
            
            # Add semantic score (0-1, already normalized)
            if semantic_scores and i < len(semantic_scores):
                score += semantic_scores[i] * 0.4  # 40% weight
            
            # Add recency bonus (0-1)
            if recency_bonus:
                source = metadata.get('source', '')
                recency = recency_bonus.get(source, 0)
                score += recency * 0.3  # 30% weight
            
            # Add position bonus (earlier results are more relevant)
            position_bonus = max(0, 1 - (i / max(len(chunks), 1)))
            score += position_bonus * 0.3  # 30% weight
            
            chunk_scores.append((i, chunk_text, metadata, tokens, score))
        
        # Check if we need to truncate
        if total_tokens <= self.max_rag_tokens:
            if debug:
                print(f"[Context] ✅ All {len(chunks)} chunks fit ({total_tokens} tokens, limit {self.max_rag_tokens})")
            return chunks, {
                "status": "no_truncation_needed",
                "total_tokens": total_tokens,
                "used_tokens": total_tokens,
                "dropped_chunks": 0,
                "max_allowed": self.max_rag_tokens,
                "dropped_details": []
            }
        
        # Sort by priority score (descending) - keep highest priority chunks
        chunk_scores.sort(key=lambda x: x[4], reverse=True)
        
        # Greedily select chunks until we hit token limit
        selected = []
        used_tokens = 0
        dropped_indices = set()
        
        for idx, chunk_text, metadata, tokens, score in chunk_scores:
            if used_tokens + tokens <= self.max_rag_tokens:
                selected.append((idx, chunk_text, metadata, tokens, score))
                used_tokens += tokens
            else:
                dropped_indices.add(idx)
        
        # Restore original order
        selected.sort(key=lambda x: x[0])
        optimized_chunks = [(text, meta) for _, text, meta, _, _ in selected]
        
        # Prepare stats
        dropped_chunks = [
            {
                "index": idx,
                "source": chunks[idx][1].get('source', 'unknown'),
                "heading": chunks[idx][1].get('heading_path', []),
                "tokens": chunk_scores[next(i for i, (ci, _, _, _, _) in enumerate(chunk_scores) if ci == idx)][3],
                "priority_score": chunk_scores[next(i for i, (ci, _, _, _, _) in enumerate(chunk_scores) if ci == idx)][4]
            }
            for idx in sorted(dropped_indices)
        ]
        
        if debug:
            print(f"[Context] ⚠️ Truncated from {total_tokens} to {used_tokens} tokens")
            print(f"  Kept: {len(selected)}/{len(chunks)} chunks")
            print(f"  Dropped: {len(dropped_indices)} chunks")
            if dropped_chunks:
                print(f"  Dropped sources: {', '.join(set(d['source'] for d in dropped_chunks))}")
        
        return optimized_chunks, {
            "status": "truncated",
            "total_tokens": total_tokens,
            "used_tokens": used_tokens,
            "dropped_chunks": len(dropped_indices),
            "max_allowed": self.max_rag_tokens,
            "dropped_details": dropped_chunks
        }
    
    def set_context_window(self, context_window: int):
        """Update context window size and recalculate limits."""
        self.context_window = context_window
        self.max_rag_tokens = int(context_window * self.reserve_percent)
        self.min_response_tokens = int(context_window * (1 - self.reserve_percent))
