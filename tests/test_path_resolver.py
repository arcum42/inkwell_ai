"""Unit tests for path_resolver module.

Tests PathResolver path normalization and resolution.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from core.path_resolver import PathResolver


class TestPathResolver:
    """Tests for PathResolver class."""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project structure for testing."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        # Create some test files
        (project_root / "file1.md").write_text("content")
        (project_root / "file2.py").write_text("code")
        
        subdir = project_root / "subdir"
        subdir.mkdir()
        (subdir / "file3.md").write_text("content")
        (subdir / "file1.md").write_text("duplicate name")
        
        nested = subdir / "nested"
        nested.mkdir()
        (nested / "deep.txt").write_text("deep content")
        
        return str(project_root)
    
    def test_normalize_quoted_paths(self, temp_project):
        """Test normalization of quoted paths."""
        resolver = PathResolver(temp_project)
        
        assert resolver.normalize_path('"file.md"') == "file.md"
        assert resolver.normalize_path("'file.md'") == "file.md"
        assert resolver.normalize_path("`file.md`") == "file.md"
        assert resolver.normalize_path("<file.md>") == "file.md"
    
    def test_normalize_relative_paths(self, temp_project):
        """Test normalization of relative paths."""
        resolver = PathResolver(temp_project)
        
        assert resolver.normalize_path("./file.md") == "file.md"
        assert resolver.normalize_path("./subdir/file.md") == "subdir/file.md"
    
    def test_normalize_backslashes(self, temp_project):
        """Test Windows-style backslash conversion."""
        resolver = PathResolver(temp_project)
        
        assert resolver.normalize_path("subdir\\file.md") == "subdir/file.md"
    
    def test_normalize_duplicate_slashes(self, temp_project):
        """Test collapsing duplicate slashes."""
        resolver = PathResolver(temp_project)
        
        assert resolver.normalize_path("subdir//file.md") == "subdir/file.md"
        assert resolver.normalize_path("//subdir/file.md") == "subdir/file.md"
    
    def test_normalize_line_markers(self, temp_project):
        """Test removal of line markers."""
        resolver = PathResolver(temp_project)
        
        assert resolver.normalize_path("file.md L10:") == "file.md"
        assert resolver.normalize_path("file.md L123:") == "file.md"
    
    def test_normalize_block_terminators(self, temp_project):
        """Test removal of block terminators."""
        resolver = PathResolver(temp_project)
        
        assert resolver.normalize_path("file.md:::END:::") == "file.md"
        assert resolver.normalize_path("file.md:::END") == "file.md"
        assert resolver.normalize_path("file.md:::") == "file.md"
    
    def test_fallback_to_active_file(self, temp_project):
        """Test fallback when path is empty."""
        resolver = PathResolver(temp_project)
        
        assert resolver.normalize_path("", "active.md") == "active.md"
        assert resolver.normalize_path("   ", "active.md") == "active.md"
    
    def test_absolute_to_relative(self, temp_project):
        """Test conversion of absolute paths to relative."""
        resolver = PathResolver(temp_project)
        
        abs_path = os.path.join(temp_project, "subdir", "file.md")
        result = resolver.normalize_path(abs_path)
        assert result == "subdir/file.md"
    
    def test_resolve_basename_single_match(self, temp_project):
        """Test resolving unique basename."""
        resolver = PathResolver(temp_project)
        
        # file2.py exists only once
        result = resolver.resolve_basename("file2.py")
        assert result == "file2.py"
    
    def test_resolve_basename_multiple_matches(self, temp_project):
        """Test resolving basename with multiple matches."""
        resolver = PathResolver(temp_project)
        
        # file1.md exists in root and subdir
        result = resolver.resolve_basename("file1.md")
        # Should return one of them (first match)
        assert result in ["file1.md", "subdir/file1.md"]
    
    def test_resolve_basename_with_active_file_context(self, temp_project):
        """Test basename resolution prefers active file directory."""
        resolver = PathResolver(temp_project)
        
        # With active file in subdir, should prefer subdir/file1.md
        result = resolver.resolve_basename("file1.md", active_file="subdir/other.md")
        assert result == "subdir/file1.md"
    
    def test_resolve_basename_not_found(self, temp_project):
        """Test resolving non-existent basename."""
        resolver = PathResolver(temp_project)
        
        result = resolver.resolve_basename("nonexistent.md")
        assert result is None
    
    def test_get_absolute_path(self, temp_project):
        """Test converting relative to absolute path."""
        resolver = PathResolver(temp_project)
        
        abs_path = resolver.get_absolute_path("subdir/file.md")
        expected = os.path.join(temp_project, "subdir", "file.md")
        assert abs_path == expected
    
    def test_is_in_project(self, temp_project):
        """Test checking if path is in project."""
        resolver = PathResolver(temp_project)
        
        # Relative path in project
        assert resolver.is_in_project("subdir/file.md") is True
        
        # Absolute path in project
        abs_path = os.path.join(temp_project, "file.md")
        assert resolver.is_in_project(abs_path) is True
        
        # Path outside project
        assert resolver.is_in_project("../outside.md") is False
        assert resolver.is_in_project("/tmp/outside.md") is False
    
    def test_refresh_index(self, temp_project):
        """Test refreshing file index."""
        resolver = PathResolver(temp_project)
        
        # Add a new file after initialization
        new_file = os.path.join(temp_project, "newfile.md")
        Path(new_file).write_text("new content")
        
        # Should not be in index yet
        result = resolver.resolve_basename("newfile.md")
        assert result is None
        
        # Refresh index
        resolver.refresh_index()
        
        # Now should be found
        result = resolver.resolve_basename("newfile.md")
        assert result == "newfile.md"
    
    def test_normalize_complex_path(self, temp_project):
        """Test normalization of complex path with multiple issues."""
        resolver = PathResolver(temp_project)
        
        complex_path = '"./subdir\\\\file.md L42: :::END:::"'
        result = resolver.normalize_path(complex_path)
        assert result == "subdir/file.md"
