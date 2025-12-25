#!/usr/bin/env python3
"""Debug hybrid search chunking."""

import os
import sys
import tempfile
from pathlib import Path

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from rag_engine import RAGEngine, MarkdownChunker

def test_chunking():
    """Test how documents are being chunked."""
    
    chunker = MarkdownChunker()
    
    # Test documents
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
    
    print("Testing Markdown Chunking")
    print("=" * 80)
    
    for filename, content in test_docs:
        print(f"\n📄 {filename}")
        print("-" * 80)
        chunks = chunker.chunk(content, filename)
        print(f"Total chunks: {len(chunks)}")
        
        for i, (chunk_text, meta) in enumerate(chunks, 1):
            lines = chunk_text.split('\n')
            preview = '\n'.join(lines[:3])
            token_count = chunker.estimate_tokens(chunk_text)
            print(f"\n  Chunk {i}:")
            print(f"    Heading Path: {' > '.join(meta.heading_path) if meta.heading_path else 'Root'}")
            print(f"    Lines: {meta.start_line}-{meta.end_line}")
            print(f"    Content Type: {meta.content_type}")
            print(f"    Tokens: {token_count}")
            print(f"    Preview: {preview[:100]}...")

if __name__ == "__main__":
    test_chunking()
