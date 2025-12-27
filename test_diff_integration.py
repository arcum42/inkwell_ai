#!/usr/bin/env python3
"""Quick test of the diff parsing system."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.diff_engine import FileEdit, EditBatch
from core.path_resolver import PathResolver
from core.diff_parser import DiffParser

# Create a temporary test project structure
import tempfile
import shutil

def test_basic_parsing():
    """Test basic UPDATE block parsing."""
    
    # Create temp project
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = os.path.join(tmpdir, "test.md")
        with open(test_file, 'w') as f:
            f.write("# Old Title\nOld content")
        
        # Mock project manager
        class MockPM:
            def read_file(self, path):
                full_path = os.path.join(tmpdir, path)
                if os.path.exists(full_path):
                    with open(full_path, 'r') as f:
                        return f.read()
                return None
        
        # Initialize parser
        resolver = PathResolver(tmpdir)
        parser = DiffParser(resolver, MockPM())
        
        # Test UPDATE block
        response = """
Here are the changes:

:::UPDATE test.md:::
# New Title
New content
:::END:::
"""
        
        batch = parser.parse_response(response)
        
        print(f"✓ Parsed {len(batch.edits)} edits")
        assert len(batch.edits) == 1
        
        edit = batch.edits[0]
        print(f"✓ Edit file: {edit.file_path}")
        assert edit.file_path == "test.md"
        
        print(f"✓ Edit type: {edit.edit_type}")
        assert edit.edit_type == "update"
        
        print(f"✓ New content length: {len(edit.new_content)}")
        assert "New Title" in edit.new_content
        
        print("\n✅ All tests passed!")

def test_multiple_edits():
    """Test parsing multiple UPDATE blocks."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        for i in range(3):
            test_file = os.path.join(tmpdir, f"file{i}.md")
            with open(test_file, 'w') as f:
                f.write(f"File {i} content")
        
        class MockPM:
            def read_file(self, path):
                full_path = os.path.join(tmpdir, path)
                if os.path.exists(full_path):
                    with open(full_path, 'r') as f:
                        return f.read()
                return None
        
        resolver = PathResolver(tmpdir)
        parser = DiffParser(resolver, MockPM())
        
        response = """
:::UPDATE file0.md:::
New content 0
:::END:::

:::UPDATE file1.md:::
New content 1
:::END:::

:::UPDATE file2.md:::
New content 2
:::END:::
"""
        
        batch = parser.parse_response(response)
        
        print(f"✓ Parsed {len(batch.edits)} edits")
        assert len(batch.edits) == 3
        
        print(f"✓ Total files affected: {batch.total_files_affected()}")
        assert batch.total_files_affected() == 3
        
        print(f"✓ All edits enabled: {batch.has_enabled_edits()}")
        assert batch.has_enabled_edits()
        
        print("\n✅ Multiple edits test passed!")

def test_structured_json():
    """Test parsing structured JSON diff_patch."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.md")
        with open(test_file, 'w') as f:
            f.write("Old content")
        
        class MockPM:
            def read_file(self, path):
                full_path = os.path.join(tmpdir, path)
                if os.path.exists(full_path):
                    with open(full_path, 'r') as f:
                        return f.read()
                return None
        
        resolver = PathResolver(tmpdir)
        parser = DiffParser(resolver, MockPM())
        
        payload = {
            "summary": "Updated test file",
            "edits": [
                {
                    "path": "test.md",
                    "after": "New content",
                    "explanation": "Updated for clarity"
                }
            ]
        }
        
        batch = parser.parse_structured_json(payload, "diff_patch")
        
        print(f"✓ Parsed structured JSON with {len(batch.edits)} edits")
        assert len(batch.edits) == 1
        
        print(f"✓ Summary: {batch.summary}")
        assert batch.summary == "Updated test file"
        
        edit = batch.edits[0]
        print(f"✓ Explanation: {edit.metadata.get('explanation')}")
        assert edit.metadata['explanation'] == "Updated for clarity"
        
        print("\n✅ Structured JSON test passed!")

if __name__ == "__main__":
    print("Testing diff parsing system...\n")
    print("=" * 60)
    print("Test 1: Basic UPDATE block parsing")
    print("=" * 60)
    test_basic_parsing()
    
    print("\n" + "=" * 60)
    print("Test 2: Multiple edits")
    print("=" * 60)
    test_multiple_edits()
    
    print("\n" + "=" * 60)
    print("Test 3: Structured JSON")
    print("=" * 60)
    test_structured_json()
    
    print("\n" + "=" * 60)
    print("🎉 All tests passed!")
    print("=" * 60)
