#!/usr/bin/env python3
"""Test LLM provider refactoring - verify both import paths work."""

import sys

def test_imports():
    """Test both old and new import paths."""
    print("Testing LLM provider imports...")
    print("-" * 50)
    
    # Test new import path
    try:
        from core.llm import LLMProvider as LLMProvider_new
        from core.llm import OllamaProvider as OllamaProvider_new
        from core.llm import LMStudioProvider as LMStudioProvider_new
        print("✓ New import path works: from core.llm import ...")
    except ImportError as e:
        print(f"✗ New import path failed: {e}")
        return False
    
    # Test old import path (backward compatibility)
    try:
        from core.llm_provider import LLMProvider as LLMProvider_old
        from core.llm_provider import OllamaProvider as OllamaProvider_old
        from core.llm_provider import LMStudioProvider as LMStudioProvider_old
        print("✓ Old import path works: from core.llm_provider import ...")
    except ImportError as e:
        print(f"✗ Old import path failed: {e}")
        return False
    
    # Verify they reference the same classes
    print("\nVerifying class identity...")
    if LLMProvider_new is LLMProvider_old:
        print("✓ LLMProvider: both paths reference same class")
    else:
        print("✗ LLMProvider: paths reference different classes!")
        return False
    
    if OllamaProvider_new is OllamaProvider_old:
        print("✓ OllamaProvider: both paths reference same class")
    else:
        print("✗ OllamaProvider: paths reference different classes!")
        return False
    
    if LMStudioProvider_new is LMStudioProvider_old:
        print("✓ LMStudioProvider: both paths reference same class")
    else:
        print("✗ LMStudioProvider: paths reference different classes!")
        return False
    
    # Test instantiation
    print("\nTesting instantiation...")
    try:
        provider = OllamaProvider_new(base_url="http://localhost:11434")
        print(f"✓ OllamaProvider instantiated: {type(provider).__name__}")
    except Exception as e:
        print(f"✗ OllamaProvider instantiation failed: {e}")
        return False
    
    try:
        provider = LMStudioProvider_new(base_url="http://localhost:1234")
        print(f"✓ LMStudioProvider instantiated: {type(provider).__name__}")
    except Exception as e:
        print(f"✗ LMStudioProvider instantiation failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("All import tests passed! ✓")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
