#!/usr/bin/env python3
"""Test script for the new tool registry system."""

from core.tool_base import get_registry
from core.tools import WebReader, WebSearcher, WikiTool, ImageSearcher


def test_tool_registry():
    """Test basic registry operations."""
    print("=" * 60)
    print("TOOL REGISTRY TEST")
    print("=" * 60)
    
    registry = get_registry()
    
    # Test 1: Tool registration
    print("\n1. Testing tool registration:")
    all_tools = registry.get_all_tools()
    print(f"   Total registered tools: {len(all_tools)}")
    for tool in all_tools:
        print(f"   - {tool.name}: {tool.description[:50]}...")
    
    # Test 2: Tool availability
    print("\n2. Testing tool availability:")
    available = registry.get_available_tools()
    unavailable = [t for t in all_tools if t not in available]
    print(f"   Available: {[t.name for t in available]}")
    print(f"   Unavailable: {[t.name for t in unavailable]}")
    
    # Test 3: Tool lookup
    print("\n3. Testing tool lookup:")
    wiki = registry.get_tool("WIKI")
    if wiki:
        print(f"   ✓ Found WIKI tool")
        print(f"     Name: {wiki.name}")
        print(f"     Available: {wiki.is_available()}")
        print(f"     Pattern: {wiki.get_usage_pattern()}")
    else:
        print(f"   ✗ WIKI tool not found")
    
    # Test 4: Unknown tool
    unknown = registry.get_tool("UNKNOWN")
    print(f"\n4. Unknown tool lookup: {unknown}")
    
    # Test 5: LLM instructions generation
    print("\n5. LLM Instructions:")
    instructions = registry.get_tool_instructions()
    print(f"   Length: {len(instructions)} chars")
    print(f"   Preview:\n{instructions[:200]}...")
    
    return True


def test_tool_execution():
    """Test executing tools."""
    print("\n" + "=" * 60)
    print("TOOL EXECUTION TEST")
    print("=" * 60)
    
    registry = get_registry()
    
    # Test Wikipedia tool
    print("\n1. Testing Wikipedia tool:")
    wiki = registry.get_tool("WIKI")
    if wiki and wiki.is_available():
        print("   Executing: wiki.execute('Python programming')")
        result_text, extra_data = wiki.execute("Python (programming language)")
        print(f"   Result length: {len(result_text)} chars")
        print(f"   Extra data: {extra_data}")
        print(f"   Preview:\n{result_text[:200]}...")
    else:
        print("   Skipped (unavailable)")
    
    # Test Web Reader
    print("\n2. Testing Web Reader tool:")
    reader = registry.get_tool("WEB_READ")
    if reader and reader.is_available():
        print("   Executing: reader.execute('https://example.com')")
        result_text, extra_data = reader.execute("https://example.com")
        print(f"   Result length: {len(result_text)} chars")
        print(f"   Extra data: {extra_data}")
        print(f"   Preview:\n{result_text[:200]}...")
    else:
        print("   Skipped (unavailable)")
    
    return True


if __name__ == "__main__":
    try:
        test_tool_registry()
        test_tool_execution()
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
