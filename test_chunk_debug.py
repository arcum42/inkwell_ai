#!/usr/bin/env python3
"""Debug why documents 2-4 return 0 chunks."""

import os
import sys
import tempfile
from pathlib import Path

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from rag_engine import MarkdownChunker

def test_chunking_debug():
    """Debug chunking with step-by-step analysis."""
    
    # Single test document
    content = """# Natural Language Processing
NLP uses machine learning to understand text.
Word embeddings and transformers are important techniques.
BERT and GPT are popular models."""
    
    chunker = MarkdownChunker()
    
    print("Testing doc2: Natural Language Processing")
    print("=" * 80)
    print(f"Content length: {len(content)} chars")
    print(f"Content:\n{content}\n")
    
    # Manual line-by-line analysis
    lines = content.split('\n')
    print(f"Total lines: {len(lines)}")
    for i, line in enumerate(lines):
        tokens = chunker.estimate_tokens(line)
        print(f"  Line {i}: {repr(line)[:60]}... ({tokens} tokens)")
    
    print(f"\nMin tokens required: {chunker.min_tokens}")
    print(f"Default tokens: {chunker.default_tokens}")
    print(f"Max tokens: {chunker.max_tokens}")
    
    # Test extraction of frontmatter
    fm, remaining = chunker._extract_frontmatter(content)
    print(f"\nFrontmatter found: {fm is not None}")
    print(f"Remaining content equals original: {remaining == content}")
    
    # Now test full chunking
    print("\nCalling chunk()...")
    chunks = chunker.chunk(content, "doc2.md")
    print(f"Result: {len(chunks)} chunks")
    
    for i, (chunk_text, meta) in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Text: {chunk_text[:100]}...")
        print(f"  Tokens: {chunker.estimate_tokens(chunk_text)}")
        print(f"  Meta: {meta}")

if __name__ == "__main__":
    test_chunking_debug()
