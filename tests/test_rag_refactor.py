#!/usr/bin/env python
"""Test that RAG refactoring maintains backward compatibility."""

import sys

try:
    # Test new import path
    from core.rag import RAGEngine, MarkdownChunker, QueryCache, ContextOptimizer
    print("✓ New import path (core.rag) works")
    
    # Test backward compatibility import path
    from core.rag_engine import RAGEngine as RAGEngineCompat
    print("✓ Backward compatibility import (core.rag_engine) works")
    
    # Verify they're the same class
    assert RAGEngine is RAGEngineCompat, "Classes should be identical"
    print("✓ Both imports reference the same class")
    
    print("\nAll import tests passed!")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ Import test failed: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
