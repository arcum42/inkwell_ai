"""Keyword-based search using BM25 algorithm."""

import math
from typing import List


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
