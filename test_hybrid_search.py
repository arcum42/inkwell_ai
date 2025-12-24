#!/usr/bin/env python3
"""Test hybrid search functionality in RAG engine."""

import os
import sys
import tempfile
from pathlib import Path

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from rag_engine import RAGEngine, MarkdownChunker

def test_hybrid_search():
    """Test hybrid search with both keyword and semantic results."""
    
    # Create temp directory for Chroma
    with tempfile.TemporaryDirectory() as tmpdir:
        rag = RAGEngine(project_path=tmpdir)
        
        # Index some test documents with different keywords
        test_docs = [
            ("doc1.md", """# Introduction to Machine Learning
Machine learning is a subset of artificial intelligence.
It focuses on building systems that can learn from data.
Neural networks are a key component of deep learning."""),
            
            ("doc2.md", """# Natural Language Processing
NLP uses machine learning to understand text.
Word embeddings and transformers are important techniques.
BERT and GPT are popular models."""),
            
            ("doc3.md", """# Database Systems
Relational databases store data in tables.
SQL is the standard query language.
NoSQL databases offer different data models."""),
            
            ("doc4.md", """# Python Programming
Python is a popular programming language.
Machine learning libraries like TensorFlow and PyTorch are written in Python.
Python's flexibility makes it great for data science."""),
        ]
        
        print("Indexing test documents...")
        for filename, content in test_docs:
            rag.index_file(filename, content)
        
        print("\n" + "="*80)
        print("Testing Hybrid Search vs Semantic-Only Search")
        print("="*80)
        
        queries = [
            "machine learning neural networks",
            "database SQL",
            "python tensorflow",
            "NLP embeddings",
        ]
        
        for query in queries:
            print(f"\n📋 Query: '{query}'")
            print("-" * 80)
            
            # Semantic-only search
            print("\n[SEMANTIC ONLY]")
            semantic_results = rag.query(query, n_results=3, use_hybrid=False, debug=True)
            for i, doc in enumerate(semantic_results, 1):
                print(f"  {i}. {doc[:100]}...")
            
            # Clear cache to force fresh hybrid search
            rag.query_cache.invalidate_all()
            
            # Hybrid search
            print("\n[HYBRID SEARCH (40% keyword + 60% semantic)]")
            hybrid_results = rag.query(query, n_results=3, use_hybrid=True, debug=True)
            for i, doc in enumerate(hybrid_results, 1):
                print(f"  {i}. {doc[:100]}...")
            
            # Check if results differ
            if semantic_results == hybrid_results:
                print("\n✅ Same ranking (keywords and semantics aligned)")
            else:
                print("\n⚠️  Different ranking (hybrid search re-ranked results)")
        
        print("\n" + "="*80)
        print("Testing BM25 Keyword Matching")
        print("="*80)
        
        # Test keyword-specific queries
        keyword_queries = [
            "table SQL",  # Should favor doc3
            "transformers BERT GPT",  # Should favor doc2
            "flexibility data science",  # Should favor doc4
        ]
        
        for query in keyword_queries:
            print(f"\n📋 Query: '{query}'")
            print("-" * 80)
            
            rag.query_cache.invalidate_all()
            results = rag.query(query, n_results=2, use_hybrid=True, debug=False)
            
            for i, doc in enumerate(results, 1):
                # Highlight keyword matches
                highlighted = doc
                for keyword in query.split():
                    if keyword.lower() in doc.lower():
                        highlighted = highlighted.replace(
                            keyword,
                            f"[{keyword}]",
                            1
                        )
                print(f"  {i}. {highlighted[:120]}...")
        
        print("\n" + "="*80)
        print("✅ All hybrid search tests completed!")
        print("="*80)

if __name__ == "__main__":
    test_hybrid_search()
