#!/usr/bin/env python3
"""Test smart context truncation and optimization."""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from rag_engine import RAGEngine, ContextOptimizer

def test_context_optimizer():
    """Test the ContextOptimizer class directly."""
    
    print("="*80)
    print("Testing ContextOptimizer Class")
    print("="*80)
    
    # Create optimizer with small context window for testing
    optimizer = ContextOptimizer(context_window=1024, reserve_percent=0.70)
    print(f"\nContext window: 1024 tokens")
    print(f"Max RAG tokens: {optimizer.max_rag_tokens} (70%)")
    print(f"Min response tokens: {optimizer.min_response_tokens} (30%)")
    
    # Create test chunks
    chunks = [
           ("This is a short chunk about machine learning. " * 10, {"source": "ml.md", "heading_path": ["ML Basics"]}),
           ("This is a longer chunk with more detailed content. " * 20, {"source": "ml.md", "heading_path": ["ML Basics"]}),
           ("Another chunk about data science and analytics. " * 20, {"source": "data.md", "heading_path": ["Data Science"]}),
           ("Yet another chunk about neural networks. " * 18, {"source": "nn.md", "heading_path": ["Neural Networks"]}),
           ("A note about Python programming and data science. " * 15, {"source": "python.md", "heading_path": ["Python"]}),
    ]
    
    print(f"\nTest chunks:")
    for i, (text, meta) in enumerate(chunks):
        tokens = optimizer.estimate_tokens(text)
        print(f"  {i+1}. {meta['source']:15s} {meta['heading_path'][0]:20s} {tokens:4d} tokens")
    
    total_tokens = sum(optimizer.estimate_tokens(text) for text, _ in chunks)
    print(f"\n  Total: {total_tokens} tokens")
    
    # Test 1: No truncation needed
    print("\n" + "-"*80)
    print("TEST 1: Context doesn't exceed limit")
    print("-"*80)
    
    small_chunks = chunks[:2]
    optimized, stats = optimizer.optimize_context(small_chunks, debug=True)
    
    print(f"\nResult:")
    print(f"  Status: {stats['status']}")
    print(f"  Original: {stats['total_tokens']} tokens")
    print(f"  Used: {stats['used_tokens']} tokens")
    print(f"  Chunks kept: {len(optimized)}/{len(small_chunks)}")
    
    # Test 2: Truncation needed
    print("\n" + "-"*80)
    print("TEST 2: Context exceeds limit - truncation required")
    print("-"*80)
    
    optimized, stats = optimizer.optimize_context(chunks, debug=True)
    
    print(f"\nResult:")
    print(f"  Status: {stats['status']}")
    print(f"  Original: {stats['total_tokens']} tokens")
    print(f"  Used: {stats['used_tokens']} tokens")
    print(f"  Chunks kept: {len(optimized)}/{len(chunks)}")
    print(f"  Dropped: {stats['dropped_chunks']}")
    if stats['dropped_details']:
        print(f"\n  Dropped chunks:")
        for dropped in stats['dropped_details']:
            print(f"    - {dropped['source']:15s} {dropped['heading'][0] if dropped['heading'] else 'Root':20s} {dropped['tokens']:4d} tokens")
    
    # Test 3: With semantic scores
    print("\n" + "-"*80)
    print("TEST 3: Truncation with semantic relevance scores")
    print("-"*80)
    
    semantic_scores = [0.95, 0.80, 0.60, 0.40, 0.20]  # First chunk most relevant
    optimized, stats = optimizer.optimize_context(
        chunks,
        semantic_scores=semantic_scores,
        debug=True
    )
    
    print(f"\nResult:")
    print(f"  Kept chunks: {len(optimized)} (prioritized by semantic relevance)")
    
    # Test 4: Different context windows
    print("\n" + "-"*80)
    print("TEST 4: Different context window sizes")
    print("-"*80)
    
    for window_size in [512, 1024, 2048]:
        optimizer.set_context_window(window_size)
        optimized, stats = optimizer.optimize_context(chunks, debug=False)
        
        used_percent = (stats['used_tokens'] / stats['max_allowed']) * 100 if stats['max_allowed'] > 0 else 0
        print(f"  {window_size:4d} token window: kept {len(optimized):2d} chunks, using {stats['used_tokens']:4d}/{stats['max_allowed']:4d} tokens ({used_percent:5.1f}%)")

def test_rag_optimized_context():
    """Test the get_optimized_context method in RAGEngine."""
    
    print("\n" + "="*80)
    print("Testing RAGEngine.get_optimized_context()")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        rag = RAGEngine(project_path=tmpdir)
        
        # Index test documents
        test_docs = [
            ("doc1.md", """# Machine Learning Basics
Machine learning is a subset of artificial intelligence.
It focuses on building systems that can learn from data.
Neural networks are a key component of deep learning.
Deep learning has revolutionized many fields."""),
            
            ("doc2.md", """# Data Science Fundamentals
Data science combines statistics, programming, and domain knowledge.
Machine learning is a key tool in data science.
Data visualization helps understand complex patterns.
Statistical methods are essential for data analysis."""),
            
            ("doc3.md", """# Python for Data Science
Python is a popular language for data science and machine learning.
Libraries like NumPy, Pandas, and TensorFlow extend Python's capabilities.
Jupyter notebooks provide an interactive environment for data exploration.
Python's simplicity makes it accessible to beginners."""),
            
            ("doc4.md", """# Advanced Neural Networks
Convolutional neural networks are used for image processing.
Recurrent neural networks excel at sequence modeling.
Transformers have become the dominant architecture for NLP.
Attention mechanisms enable better context understanding.
Transfer learning reuses pre-trained models for new tasks."""),
        ]
        
        print("\nIndexing test documents...")
        for filename, content in test_docs:
            rag.index_file(filename, content)
        
        # Test 1: Query with small context window
        print("\n" + "-"*80)
        print("TEST 1: Query with small context window (512 tokens)")
        print("-"*80)
        
        query = "machine learning neural networks"
        optimized_chunks, stats = rag.get_optimized_context(
            query,
            n_results=5,
            context_window=512,
            debug=True
        )
        
        print(f"\nOptimized context:")
        print(f"  Chunks: {len(optimized_chunks)}")
        print(f"  Total tokens: {stats['total_tokens']}")
        print(f"  Used tokens: {stats['used_tokens']}")
        print(f"  Utilization: {(stats['used_tokens']/512)*100:.1f}%")
        
        # Test 2: Query with large context window
        print("\n" + "-"*80)
        print("TEST 2: Query with large context window (4096 tokens)")
        print("-"*80)
        
        optimized_chunks, stats = rag.get_optimized_context(
            query,
            n_results=5,
            context_window=4096,
            debug=True
        )
        
        print(f"\nOptimized context:")
        print(f"  Chunks: {len(optimized_chunks)}")
        print(f"  Total tokens: {stats['total_tokens']}")
        print(f"  Used tokens: {stats['used_tokens']}")
        print(f"  Utilization: {(stats['used_tokens']/4096)*100:.1f}%")
        
        # Test 3: Set context window on engine
        print("\n" + "-"*80)
        print("TEST 3: Set persistent context window")
        print("-"*80)
        
        rag.set_context_window(1024)
        print(f"Set engine context window to 1024 tokens")
        
        optimized_chunks, stats = rag.get_optimized_context(
            query,
            n_results=5,
            debug=True
        )
        
        print(f"\nOptimized context (using persisted window):")
        print(f"  Chunks: {len(optimized_chunks)}")
        print(f"  Used tokens: {stats['used_tokens']} / {stats['max_allowed']}")
        
        # Test 4: Recency tracking
        print("\n" + "-"*80)
        print("TEST 4: Recency-based prioritization")
        print("-"*80)
        
        # Simulate time passing
        print("\nSimulating recency decay:")
        time.sleep(0.1)  # Small delay
        
        # First query - all files get current timestamp
        optimized_chunks, stats = rag.get_optimized_context(
            query,
            n_results=5,
            context_window=2048,
            debug=False
        )
        
        print(f"  Query 1: {len(optimized_chunks)} chunks kept")
        print(f"  Tracked files: {len(rag._file_access_times)}")
        
        # Second query immediately after - should prioritize same files
        optimized_chunks, stats = rag.get_optimized_context(
            query,
            n_results=5,
            context_window=2048,
            debug=False
        )
        
        print(f"  Query 2: {len(optimized_chunks)} chunks kept")
        print(f"  Files will use recent timestamp bonuses")
        
        print("\n" + "="*80)
        print("✅ All context optimization tests completed!")
        print("="*80)

if __name__ == "__main__":
    test_context_optimizer()
    test_rag_optimized_context()
