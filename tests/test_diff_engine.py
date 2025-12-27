"""Unit tests for diff_engine module.

Tests FileEdit and EditBatch dataclasses.
"""

import pytest
from datetime import datetime
from core.diff_engine import FileEdit, EditBatch


class TestFileEdit:
    """Tests for FileEdit dataclass."""
    
    def test_create_basic_edit(self):
        """Test creating a basic FileEdit."""
        edit = FileEdit(
            edit_id="test123",
            file_path="test.md",
            old_content="old content",
            new_content="new content",
            edit_type="update",
        )
        
        assert edit.edit_id == "test123"
        assert edit.file_path == "test.md"
        assert edit.edit_type == "update"
        assert edit.enabled is True
    
    def test_compute_diff_stats_new_file(self):
        """Test diff stats for new file."""
        edit = FileEdit(
            edit_id="1",
            file_path="new.md",
            old_content=None,
            new_content="line1\nline2\nline3",
            edit_type="create",
        )
        
        added, deleted, changed = edit.compute_diff_stats()
        assert added == 3
        assert deleted == 0
        assert changed == 0
    
    def test_compute_diff_stats_deleted_file(self):
        """Test diff stats for deleted file."""
        edit = FileEdit(
            edit_id="1",
            file_path="old.md",
            old_content="line1\nline2",
            new_content="",
            edit_type="delete",
        )
        
        added, deleted, changed = edit.compute_diff_stats()
        assert added == 0
        assert deleted == 2
    
    def test_compute_diff_stats_update(self):
        """Test diff stats for file update."""
        edit = FileEdit(
            edit_id="1",
            file_path="file.md",
            old_content="line1\nline2\nline3",
            new_content="line1\nmodified line2\nline3\nline4",
            edit_type="update",
        )
        
        added, deleted, changed = edit.compute_diff_stats()
        # Should have additions and deletions/changes
        assert added > 0
        assert deleted >= 0
    
    def test_has_changes(self):
        """Test has_changes detection."""
        # Edit with changes
        edit1 = FileEdit(
            edit_id="1",
            file_path="file.md",
            old_content="old",
            new_content="new",
            edit_type="update",
        )
        assert edit1.has_changes() is True
        
        # Edit without changes
        edit2 = FileEdit(
            edit_id="2",
            file_path="file.md",
            old_content="same",
            new_content="same",
            edit_type="update",
        )
        assert edit2.has_changes() is False
        
        # New file with content
        edit3 = FileEdit(
            edit_id="3",
            file_path="new.md",
            old_content=None,
            new_content="content",
            edit_type="create",
        )
        assert edit3.has_changes() is True
    
    def test_get_summary(self):
        """Test summary generation."""
        edit = FileEdit(
            edit_id="1",
            file_path="file.md",
            old_content="line1\nline2",
            new_content="line1\nmodified\nline3",
            edit_type="update",
        )
        
        summary = edit.get_summary()
        # Summary should contain diff stats like "+1 / -0 / ~1"
        assert "+" in summary and "/" in summary


class TestEditBatch:
    """Tests for EditBatch dataclass."""
    
    def test_create_batch(self):
        """Test creating an EditBatch."""
        edit1 = FileEdit("1", "file1.md", "old", "new", "update")
        edit2 = FileEdit("2", "file2.md", None, "content", "create")
        
        batch = EditBatch(
            batch_id="batch1",
            edits=[edit1, edit2],
            summary="Test changes",
        )
        
        assert batch.batch_id == "batch1"
        assert len(batch.edits) == 2
        assert batch.summary == "Test changes"
    
    def test_get_enabled_edits(self):
        """Test filtering enabled edits."""
        edit1 = FileEdit("1", "file1.md", "old", "new", "update", enabled=True)
        edit2 = FileEdit("2", "file2.md", "old", "new", "update", enabled=False)
        edit3 = FileEdit("3", "file3.md", "old", "new", "update", enabled=True)
        
        batch = EditBatch("batch1", [edit1, edit2, edit3])
        
        enabled = batch.get_enabled_edits()
        assert len(enabled) == 2
        assert edit2 not in enabled
    
    def test_total_files_affected(self):
        """Test counting affected files."""
        edit1 = FileEdit("1", "file1.md", "old", "new", "update")
        edit2 = FileEdit("2", "file1.md", "old", "newer", "update")  # Same file
        edit3 = FileEdit("3", "file2.md", None, "content", "create")
        
        batch = EditBatch("batch1", [edit1, edit2, edit3])
        
        assert batch.total_files_affected() == 2  # file1.md and file2.md
    
    def test_total_enabled_files(self):
        """Test counting enabled files."""
        edit1 = FileEdit("1", "file1.md", "old", "new", "update", enabled=True)
        edit2 = FileEdit("2", "file2.md", "old", "new", "update", enabled=False)
        edit3 = FileEdit("3", "file3.md", "old", "new", "update", enabled=True)
        
        batch = EditBatch("batch1", [edit1, edit2, edit3])
        
        assert batch.total_enabled_files() == 2
    
    def test_get_cumulative_stats(self):
        """Test cumulative statistics."""
        edit1 = FileEdit("1", "file1.md", None, "line1\nline2", "create", enabled=True)
        edit2 = FileEdit("2", "file2.md", "old", "new", "update", enabled=True)
        edit3 = FileEdit("3", "file3.md", "a", "b", "update", enabled=False)  # Disabled
        
        batch = EditBatch("batch1", [edit1, edit2, edit3])
        
        added, deleted, changed = batch.get_cumulative_stats()
        # Should count edit1 and edit2 but not edit3
        assert added >= 2  # At least 2 lines from edit1
    
    def test_has_enabled_edits(self):
        """Test checking for enabled edits."""
        edit1 = FileEdit("1", "file1.md", "old", "new", "update", enabled=False)
        edit2 = FileEdit("2", "file2.md", "old", "new", "update", enabled=False)
        
        batch = EditBatch("batch1", [edit1, edit2])
        assert batch.has_enabled_edits() is False
        
        edit1.enabled = True
        assert batch.has_enabled_edits() is True
    
    def test_enable_disable_all(self):
        """Test enabling/disabling all edits."""
        edit1 = FileEdit("1", "file1.md", "old", "new", "update", enabled=True)
        edit2 = FileEdit("2", "file2.md", "old", "new", "update", enabled=True)
        
        batch = EditBatch("batch1", [edit1, edit2])
        
        batch.disable_all()
        assert all(not edit.enabled for edit in batch.edits)
        
        batch.enable_all()
        assert all(edit.enabled for edit in batch.edits)
    
    def test_get_edits_for_file(self):
        """Test filtering edits by file."""
        edit1 = FileEdit("1", "file1.md", "old", "new", "update")
        edit2 = FileEdit("2", "file2.md", "old", "new", "update")
        edit3 = FileEdit("3", "file1.md", "old", "newer", "update")
        
        batch = EditBatch("batch1", [edit1, edit2, edit3])
        
        file1_edits = batch.get_edits_for_file("file1.md")
        assert len(file1_edits) == 2
        assert edit2 not in file1_edits
