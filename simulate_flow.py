#!/usr/bin/env python3
"""Simulate the exact application flow to debug batch mode."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

# Create app for QSettings
app = QApplication(sys.argv)

# Get settings
settings = QSettings("InkwellAI", "InkwellAI")
project_path = settings.value("last_project", "")

if not project_path or not os.path.exists(project_path):
    project_path = os.path.join(os.path.dirname(__file__), "test_project")

print("=" * 70)
print("SIMULATING APPLICATION FLOW")
print("=" * 70)

# Mock ProjectManager
class MockProjectManager:
    def __init__(self):
        self.root_path = None
    
    def open_project(self, path):
        self.root_path = path
        return True
    
    def read_file(self, rel_path):
        if not self.root_path:
            return None
        full_path = os.path.join(self.root_path, rel_path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                return f.read()
        return None

# Mock Window
class MockWindow:
    def __init__(self):
        self.project_manager = MockProjectManager()

# Step 1: ChatController.__init__
print("\n1. ChatController.__init__()")
print("   - Creating ChatController...")

from core.path_resolver import PathResolver
from core.diff_parser import DiffParser

class SimulatedChatController:
    def __init__(self, window):
        self.window = window
        self.settings = settings
        self._diff_parser = None
        self._path_resolver = None
        self._init_diff_system()
        self.pending_edit_batches = {}
    
    def _init_diff_system(self):
        """Initialize the diff parsing system."""
        if self.window.project_manager.root_path:
            self._path_resolver = PathResolver(self.window.project_manager.root_path)
            self._diff_parser = DiffParser(self._path_resolver, self.window.project_manager)
            print(f"   DEBUG: Diff system initialized with project root: {self.window.project_manager.root_path}")
        else:
            print("   DEBUG: Cannot initialize diff system - no project root")
    
    def reinit_diff_system(self):
        """Reinitialize diff system after project change."""
        print("   - reinit_diff_system() called")
        self._init_diff_system()
    
    def _use_batch_mode(self):
        """Check if batch mode is enabled."""
        enabled = self.settings.value("use_batch_diff_dialog", True, type=bool)
        print(f"   DEBUG: Batch mode enabled: {enabled}, diff_parser exists: {self._diff_parser is not None}")
        return enabled and self._diff_parser is not None

window = MockWindow()
chat_controller = SimulatedChatController(window)

print(f"   ✓ ChatController created")
print(f"   - diff_parser: {chat_controller._diff_parser}")
print(f"   - path_resolver: {chat_controller._path_resolver}")

# Step 2: Project opens
print(f"\n2. Project opens: {project_path}")
print("   - Opening project...")

window.project_manager.open_project(project_path)
print(f"   ✓ Project opened, root_path set: {window.project_manager.root_path}")

print("   - Calling chat_controller.reinit_diff_system()...")
chat_controller.reinit_diff_system()

print(f"   ✓ After reinit:")
print(f"   - diff_parser: {chat_controller._diff_parser}")
print(f"   - path_resolver: {chat_controller._path_resolver}")

# Step 3: Check batch mode
print("\n3. Checking batch mode")
batch_mode = chat_controller._use_batch_mode()
print(f"   ✓ Batch mode active: {batch_mode}")

# Step 4: Test parsing
if chat_controller._diff_parser:
    print("\n4. Testing parse_response()")
    
    test_response = """
Here are the changes:

:::UPDATE outline.md:::
# Updated Outline
This is new content
:::END:::

:::UPDATE Summary.md:::
# Updated Summary
More new content
:::END:::
"""
    
    print(f"   - Parsing test response...")
    try:
        batch = chat_controller._diff_parser.parse_response(test_response, None)
        print(f"   ✓ Parsed successfully!")
        print(f"   - Batch ID: {batch.batch_id}")
        print(f"   - Edits: {len(batch.edits)}")
        print(f"   - Files affected: {batch.total_files_affected()}")
        
        # Simulate storing batch
        batch_id = batch.batch_id
        chat_controller.pending_edit_batches[batch_id] = batch
        
        # Simulate creating batch link
        files_affected = batch.total_files_affected()
        total_edits = len(batch.edits)
        batch_link = f'<a href="batch:{batch_id}">📝 Review {total_edits} Changes to {files_affected} Files</a>'
        
        print(f"\n   ✓ Would create link:")
        print(f"   {batch_link}")
        
        print("\n5. Testing structured JSON")
        payload = {
            "summary": "Test updates",
            "edits": [
                {"path": "outline.md", "after": "# New Title\nContent"},
                {"path": "Summary.md", "after": "# Summary\nMore content"}
            ]
        }
        
        batch2 = chat_controller._diff_parser.parse_structured_json(payload, "diff_patch")
        print(f"   ✓ Structured JSON parsed!")
        print(f"   - Batch ID: {batch2.batch_id}")
        print(f"   - Summary: {batch2.summary}")
        print(f"   - Edits: {len(batch2.edits)}")
        
    except Exception as e:
        print(f"   ✗ Parse failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n4. ✗ Cannot test parsing - diff_parser is None")

print("\n" + "=" * 70)
print("SIMULATION COMPLETE")
print("=" * 70)

if chat_controller._diff_parser and batch_mode:
    print("\n✅ SUCCESS: Batch mode should work in the real application")
    print("   - diff_parser is initialized")
    print("   - batch mode is enabled")
    print("   - parsing works correctly")
else:
    print("\n⚠️  PROBLEM DETECTED:")
    if not chat_controller._diff_parser:
        print("   - diff_parser is None")
    if not batch_mode:
        print("   - batch mode is disabled or diff_parser missing")

print("\n" + "=" * 70)
