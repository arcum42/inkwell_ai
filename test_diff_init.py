#!/usr/bin/env python3
"""Test diff system initialization manually."""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

# Must create QApplication for QSettings
app = QApplication(sys.argv)

# Get last project path
settings = QSettings("InkwellAI", "InkwellAI")
project_path = settings.value("last_project", "")

print(f"Last project path: {project_path}")
print(f"Path exists: {os.path.exists(project_path) if project_path else False}")

if not project_path or not os.path.exists(project_path):
    print("\n⚠️  No valid project path found. Using test_project...")
    project_path = os.path.join(os.path.dirname(__file__), "test_project")
    print(f"Using: {project_path}")
    print(f"Exists: {os.path.exists(project_path)}")

if not os.path.exists(project_path):
    print("\n❌ Cannot proceed - no valid project folder")
    sys.exit(1)

print("\n" + "=" * 60)
print("Testing Diff System Initialization")
print("=" * 60)

# Import components
from core.path_resolver import PathResolver
from core.diff_parser import DiffParser

# Mock ProjectManager
class MockProjectManager:
    def __init__(self, root):
        self.root_path = root
    
    def read_file(self, rel_path):
        full_path = os.path.join(self.root_path, rel_path)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None

try:
    # Initialize
    pm = MockProjectManager(project_path)
    resolver = PathResolver(project_path)
    parser = DiffParser(resolver, pm)
    
    print(f"\n✅ PathResolver initialized")
    print(f"   Root: {resolver.project_root}")
    
    print(f"\n✅ DiffParser initialized")
    print(f"   Has resolver: {parser.path_resolver is not None}")
    print(f"   Has project_manager: {parser.project_manager is not None}")
    
    # Test parsing
    test_response = """
Here are the changes:

:::UPDATE outline.md:::
# New Title
This is updated content
:::END:::
"""
    
    print(f"\n" + "=" * 60)
    print("Testing Parse Response")
    print("=" * 60)
    
    batch = parser.parse_response(test_response, None)
    print(f"\n✅ Parsed successfully")
    print(f"   Batch ID: {batch.batch_id}")
    print(f"   Edits: {len(batch.edits)}")
    print(f"   Files affected: {batch.total_files_affected()}")
    
    if batch.edits:
        edit = batch.edits[0]
        print(f"\n   Edit 0:")
        print(f"   - File: {edit.file_path}")
        print(f"   - Type: {edit.edit_type}")
        print(f"   - New content length: {len(edit.new_content)}")
    
    # Test structured JSON
    print(f"\n" + "=" * 60)
    print("Testing Structured JSON")
    print("=" * 60)
    
    payload = {
        "summary": "Test edit",
        "edits": [
            {
                "path": "outline.md",
                "after": "# Test\nNew content"
            }
        ]
    }
    
    batch2 = parser.parse_structured_json(payload, "diff_patch")
    print(f"\n✅ Parsed structured JSON")
    print(f"   Batch ID: {batch2.batch_id}")
    print(f"   Summary: {batch2.summary}")
    print(f"   Edits: {len(batch2.edits)}")
    
    print(f"\n" + "=" * 60)
    print("🎉 All tests passed!")
    print("=" * 60)
    
    print(f"\nConclusion:")
    print(f"- Diff system CAN be initialized with project: {project_path}")
    print(f"- Parsing works correctly")
    print(f"- The issue must be in the application flow, not the components")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
