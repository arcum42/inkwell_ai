"""Core data models for diff/patch handling.

Provides unified representation of file edits regardless of source format
(UPDATE blocks, PATCH blocks, unified diffs, or structured JSON).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Any
import difflib


@dataclass
class FileEdit:
    """Represents a proposed edit to a single file.
    
    Attributes:
        edit_id: Unique identifier for this edit
        file_path: Normalized path relative to project root
        old_content: Current file content (None for new files)
        new_content: Proposed new content
        edit_type: Type of operation (update, create, delete)
        metadata: Additional info (source format, line ranges, explanations, etc.)
        enabled: Whether this edit should be applied in batch operations
    """
    edit_id: str
    file_path: str
    old_content: str | None
    new_content: str
    edit_type: Literal["update", "create", "delete"]
    metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def compute_diff_stats(self) -> tuple[int, int, int]:
        """Compute diff statistics.
        
        Returns:
            Tuple of (added_lines, deleted_lines, changed_lines)
        """
        if self.old_content is None:
            # New file - all lines are additions
            new_lines = self.new_content.splitlines()
            return len(new_lines), 0, 0
        
        if self.edit_type == "delete":
            # Deleted file - all lines are deletions
            old_lines = self.old_content.splitlines()
            return 0, len(old_lines), 0
        
        # Compute diff for updates
        old_lines = self.old_content.splitlines()
        new_lines = self.new_content.splitlines()
        
        added = 0
        deleted = 0
        changed = 0
        
        differ = difflib.Differ()
        for line in differ.compare(old_lines, new_lines):
            if line.startswith('+ '):
                added += 1
            elif line.startswith('- '):
                deleted += 1
            elif line.startswith('? '):
                # Marker for changed lines
                changed += 1
        
        return added, deleted, changed
    
    def has_changes(self) -> bool:
        """Check if this edit actually changes the file content.
        
        Returns:
            True if content is different, False otherwise
        """
        if self.edit_type == "create":
            return bool(self.new_content.strip())
        if self.edit_type == "delete":
            return True
        return self.old_content != self.new_content
    
    def get_summary(self) -> str:
        """Get human-readable summary of this edit.
        
        Returns:
            Summary string like "+12 / -5 / ~3"
        """
        added, deleted, changed = self.compute_diff_stats()
        return f"+{added} / -{deleted} / ~{changed}"


@dataclass
class EditBatch:
    """Collection of related file edits that should be reviewed together.
    
    Represents all edits from a single LLM response that proposed changes
    to multiple files.
    
    Attributes:
        batch_id: Unique identifier for this batch
        edits: List of FileEdit objects in this batch
        summary: Optional summary/explanation of all changes
        timestamp: When this batch was created
    """
    batch_id: str
    edits: list[FileEdit]
    summary: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_enabled_edits(self) -> list[FileEdit]:
        """Get only the edits marked as enabled.
        
        Returns:
            List of enabled FileEdit objects
        """
        return [edit for edit in self.edits if edit.enabled]
    
    def total_files_affected(self) -> int:
        """Count unique files affected by this batch.
        
        Returns:
            Number of unique file paths
        """
        return len(set(edit.file_path for edit in self.edits))
    
    def total_enabled_files(self) -> int:
        """Count unique files affected by enabled edits.
        
        Returns:
            Number of unique file paths in enabled edits
        """
        return len(set(edit.file_path for edit in self.get_enabled_edits()))
    
    def get_cumulative_stats(self) -> tuple[int, int, int]:
        """Get combined statistics for all enabled edits.
        
        Returns:
            Tuple of (total_added, total_deleted, total_changed)
        """
        total_added = 0
        total_deleted = 0
        total_changed = 0
        
        for edit in self.get_enabled_edits():
            added, deleted, changed = edit.compute_diff_stats()
            total_added += added
            total_deleted += deleted
            total_changed += changed
        
        return total_added, total_deleted, total_changed
    
    def has_enabled_edits(self) -> bool:
        """Check if any edits are enabled.
        
        Returns:
            True if at least one edit is enabled
        """
        return any(edit.enabled for edit in self.edits)
    
    def enable_all(self):
        """Enable all edits in this batch."""
        for edit in self.edits:
            edit.enabled = True
    
    def disable_all(self):
        """Disable all edits in this batch."""
        for edit in self.edits:
            edit.enabled = False
    
    def get_edits_for_file(self, file_path: str) -> list[FileEdit]:
        """Get all edits affecting a specific file.
        
        Args:
            file_path: Path to filter by
            
        Returns:
            List of FileEdit objects for that file
        """
        return [edit for edit in self.edits if edit.file_path == file_path]
