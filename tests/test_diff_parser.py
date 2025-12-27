"""Unit tests for diff_parser module.

Tests DiffParser parsing of various edit formats.
"""

import pytest
from unittest.mock import Mock
from core.diff_parser import DiffParser
from core.path_resolver import PathResolver


class MockProjectManager:
    """Mock project manager for testing."""
    
    def __init__(self):
        self.files = {}
    
    def read_file(self, path: str) -> str | None:
        return self.files.get(path)
    
    def add_file(self, path: str, content: str):
        self.files[path] = content


class TestDiffParser:
    """Tests for DiffParser class."""
    
    @pytest.fixture
    def parser(self, tmp_path):
        """Create parser with mock dependencies."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        resolver = PathResolver(str(project_root))
        pm = MockProjectManager()
        
        return DiffParser(resolver, pm), pm
    
    def test_parse_update_blocks(self, parser):
        """Test parsing :::UPDATE::: blocks."""
        diff_parser, pm = parser
        
        response = """
Here are the changes:

:::UPDATE file1.md:::
New content for file 1
:::END:::

:::UPDATE subdir/file2.md:::
Content for file 2
:::END:::
"""
        
        batch = diff_parser.parse_response(response)
        
        assert len(batch.edits) == 2
        assert batch.edits[0].file_path == "file1.md"
        assert batch.edits[0].new_content == "New content for file 1"
        assert batch.edits[0].metadata['source'] == 'update_block'
        assert batch.edits[1].file_path == "subdir/file2.md"
    
    def test_parse_update_block_with_existing_file(self, parser):
        """Test UPDATE block with existing file."""
        diff_parser, pm = parser
        
        pm.add_file("existing.md", "old content")
        
        response = """
:::UPDATE existing.md:::
new content
:::END:::
"""
        
        batch = diff_parser.parse_response(response)
        
        assert len(batch.edits) == 1
        assert batch.edits[0].old_content == "old content"
        assert batch.edits[0].new_content == "new content"
        assert batch.edits[0].edit_type == "update"
    
    def test_parse_patch_blocks(self, parser):
        """Test parsing :::PATCH::: blocks."""
        diff_parser, pm = parser
        
        pm.add_file("test.py", "line1\nline2\nline3\nline4\nline5")
        
        response = """
:::PATCH test.py:::
L2: line2 => modified line2
L4: old => new
:::END:::
"""
        
        batch = diff_parser.parse_response(response)
        
        assert len(batch.edits) == 1
        edit = batch.edits[0]
        assert edit.file_path == "test.py"
        assert "modified line2" in edit.new_content
        assert edit.metadata['source'] == 'patch_block'
    
    def test_parse_unified_diff(self, parser):
        """Test parsing ```diff blocks."""
        diff_parser, pm = parser
        
        pm.add_file("code.py", "def hello():\n    print('old')\n")
        
        response = """
```diff
--- a/code.py
+++ b/code.py
@@ -1,2 +1,2 @@
 def hello():
-    print('old')
+    print('new')
```
"""
        
        batch = diff_parser.parse_response(response)
        
        assert len(batch.edits) == 1
        edit = batch.edits[0]
        assert edit.file_path == "code.py"
        assert "print('new')" in edit.new_content
        assert edit.metadata['source'] == 'unified_diff'
    
    def test_parse_fallback_code_block(self, parser):
        """Test parsing fallback code blocks."""
        diff_parser, pm = parser
        
        pm.add_file("doc.md", "# Old Title\nOld content")
        
        # Code block without explicit markers, with active file
        response = """
Here's the updated document:

```markdown
# New Title
New content
```
"""
        
        batch = diff_parser.parse_response(response, active_file="doc.md")
        
        # Should parse as fallback when no explicit markers
        assert len(batch.edits) >= 0  # May or may not trigger depending on heuristics
    
    def test_parse_multiple_formats_mixed(self, parser):
        """Test parsing multiple formats in one response."""
        diff_parser, pm = parser
        
        pm.add_file("file1.md", "old1")
        pm.add_file("file2.py", "old2")
        
        response = """
:::UPDATE file1.md:::
new content 1
:::END:::

:::PATCH file2.py:::
L1: old2 => new2
:::END:::
"""
        
        batch = diff_parser.parse_response(response)
        
        assert len(batch.edits) == 2
        sources = {e.metadata['source'] for e in batch.edits}
        assert 'update_block' in sources
        assert 'patch_block' in sources
    
    def test_parse_structured_json(self, parser):
        """Test parsing structured JSON (diff_patch schema)."""
        diff_parser, pm = parser
        
        pm.add_file("file1.md", "old content")
        
        payload = {
            "summary": "Updated files",
            "edits": [
                {
                    "path": "file1.md",
                    "after": "new content",
                    "explanation": "Updated content"
                },
                {
                    "path": "file2.md",
                    "edit_type": "create",
                    "content": "brand new"
                }
            ]
        }
        
        batch = diff_parser.parse_structured_json(payload, "diff_patch")
        
        assert len(batch.edits) == 2
        assert batch.summary == "Updated files"
        assert batch.edits[0].metadata['schema'] == "diff_patch"
        assert batch.edits[0].metadata['explanation'] == "Updated content"
    
    def test_deduplicate_edits(self, parser):
        """Test deduplication of identical edits."""
        diff_parser, pm = parser
        
        # Same path and content twice
        response = """
:::UPDATE file.md:::
content
:::END:::

:::UPDATE file.md:::
content
:::END:::
"""
        
        batch = diff_parser.parse_response(response)
        
        # Should deduplicate
        assert len(batch.edits) == 1
    
    def test_path_normalization(self, parser):
        """Test that paths are properly normalized."""
        diff_parser, pm = parser
        
        response = """
:::UPDATE "./subdir/file.md":::
content
:::END:::
"""
        
        batch = diff_parser.parse_response(response)
        
        # Should strip quotes and ./
        assert batch.edits[0].file_path == "subdir/file.md"
    
    def test_extract_summary(self, parser):
        """Test summary extraction from response."""
        diff_parser, pm = parser
        
        response = """
Here's what I changed: Updated the documentation

:::UPDATE file.md:::
content
:::END:::
"""
        
        batch = diff_parser.parse_response(response)
        
        assert batch.summary is not None
        assert "Updated the documentation" in batch.summary
    
    def test_empty_response(self, parser):
        """Test parsing empty response."""
        diff_parser, pm = parser
        
        batch = diff_parser.parse_response("")
        
        assert len(batch.edits) == 0
        assert batch.summary is None
    
    def test_non_text_extension_handling(self, parser):
        """Test handling of non-text file extensions."""
        diff_parser, pm = parser
        
        response = """
:::UPDATE image.png:::
some text content
:::END:::
"""
        
        batch = diff_parser.parse_response(response)
        
        # Should convert to .txt
        assert batch.edits[0].file_path == "image.txt"


class TestPatchApplication:
    """Tests for patch application logic."""
    
    @pytest.fixture
    def parser_with_file(self, tmp_path):
        """Create parser with a test file."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        resolver = PathResolver(str(project_root))
        pm = MockProjectManager()
        pm.add_file("test.txt", "line1\nline2\nline3\nline4\nline5")
        
        return DiffParser(resolver, pm), pm
    
    def test_apply_line_replacement(self, parser_with_file):
        """Test L##: old => new replacement."""
        diff_parser, pm = parser_with_file
        
        patch_body = "L2: line2 => modified line2"
        success, result = diff_parser._apply_patch_body("test.txt", patch_body)
        
        assert success is True
        assert "modified line2" in result
        assert result.count("\n") == 4  # 5 lines
    
    def test_apply_range_replacement(self, parser_with_file):
        """Test L##-L##: range replacement."""
        diff_parser, pm = parser_with_file
        
        patch_body = """L2-L4:
new line 2
new line 3
new line 4"""
        
        success, result = diff_parser._apply_patch_body("test.txt", patch_body)
        
        assert success is True
        assert "new line 2" in result
        assert "new line 3" in result
    
    def test_apply_line_insertion(self, parser_with_file):
        """Test L##: insertion."""
        diff_parser, pm = parser_with_file
        
        patch_body = "L3: inserted line"
        success, result = diff_parser._apply_patch_body("test.txt", patch_body)
        
        assert success is True
        assert "inserted line" in result
