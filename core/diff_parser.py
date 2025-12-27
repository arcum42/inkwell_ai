"""Unified parser for all diff/patch formats.

Handles parsing of:
- :::UPDATE path::: ... :::END::: blocks
- :::PATCH path::: with L##: directives
- ```diff unified diff blocks
- Structured JSON (diff_patch schema)
- Fallback code blocks
"""

import os
import re
import uuid
from datetime import datetime
from typing import Any

from core.diff_engine import FileEdit, EditBatch
from core.path_resolver import PathResolver


class DiffParser:
    """Unified parser for all diff/patch formats.
    
    Detects and parses various edit formats from LLM responses,
    converting them to a unified EditBatch representation.
    """
    
    def __init__(self, path_resolver: PathResolver, project_manager=None):
        """Initialize parser.
        
        Args:
            path_resolver: PathResolver instance for normalizing paths
            project_manager: Optional ProjectManager for reading file contents
        """
        self.path_resolver = path_resolver
        self.project_manager = project_manager
    
    def parse_response(self, response: str, active_file: str | None = None) -> EditBatch:
        """Main entry point - parse response and create EditBatch.
        
        Detects all edit formats in the response and combines them
        into a single batch.
        
        Args:
            response: Raw LLM response text
            active_file: Currently active file path (for context)
            
        Returns:
            EditBatch containing all detected edits
        """
        all_edits: list[FileEdit] = []
        
        # Parse each format (order matters - more specific first)
        all_edits.extend(self._parse_update_blocks(response, active_file))
        all_edits.extend(self._parse_patch_blocks(response, active_file))
        all_edits.extend(self._parse_unified_diffs(response, active_file))
        
        # Fallback: parse code blocks only if no explicit edits found
        if not all_edits and active_file:
            all_edits.extend(self._parse_fallback_code_blocks(response, active_file))
        
        # Deduplicate by (path, content) pairs
        unique_edits = self._deduplicate_edits(all_edits)
        
        batch = EditBatch(
            batch_id=str(uuid.uuid4()),
            edits=unique_edits,
            summary=self._extract_summary(response),
            timestamp=datetime.now(),
        )
        
        return batch
    
    def parse_structured_json(self, payload: dict, schema_id: str) -> EditBatch:
        """Parse structured JSON response (diff_patch schema).
        
        Args:
            payload: Parsed JSON payload
            schema_id: Schema identifier (e.g., 'diff_patch', 'diff_patch_v2')
            
        Returns:
            EditBatch with edits from structured data
        """
        edits = []
        summary = payload.get('summary')
        
        for item in payload.get('edits', []):
            path = item.get('path', '')
            if not path:
                continue
            
            # Normalize path
            normalized_path = self.path_resolver.normalize_path(path)
            
            # Determine edit type
            edit_type = item.get('edit_type', 'update')
            if edit_type not in ('update', 'create', 'delete'):
                edit_type = 'update'
            
            # Get content
            new_content = item.get('after', '') or item.get('content', '')
            
            # Try to read old content
            old_content = None
            if self.project_manager and edit_type != 'create':
                try:
                    old_content = self.project_manager.read_file(normalized_path)
                except Exception:
                    pass
            
            # Create edit
            edit = FileEdit(
                edit_id=str(uuid.uuid4()),
                file_path=normalized_path,
                old_content=old_content,
                new_content=new_content,
                edit_type=edit_type,
                metadata={
                    'source': 'structured_json',
                    'schema': schema_id,
                    'explanation': item.get('explanation', ''),
                    'before': item.get('before', ''),
                    'warnings': item.get('warnings', []),
                },
                enabled=True,
            )
            
            edits.append(edit)
        
        return EditBatch(
            batch_id=str(uuid.uuid4()),
            edits=edits,
            summary=summary,
            timestamp=datetime.now(),
        )
    
    def _parse_update_blocks(self, response: str, active_file: str | None) -> list[FileEdit]:
        """Parse :::UPDATE path::: ... :::END::: blocks.
        
        Format:
            :::UPDATE path/to/file.md:::
            New content here
            :::END:::
        
        Args:
            response: Response text
            active_file: Active file for path context
            
        Returns:
            List of FileEdit objects
        """
        pattern = r":::UPDATE\s*(.*?)\s*:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
        matches = re.findall(pattern, response, re.DOTALL)
        
        edits = []
        for raw_path, content in matches:
            path = self.path_resolver.normalize_path(raw_path.strip(), active_file)
            content = content.strip().replace('\\n', '\n')
            
            # Check for non-text extensions
            file_ext = os.path.splitext(path)[1].lower()
            non_text_ext = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                           '.mp4', '.avi', '.mov', '.mp3', '.wav',
                           '.pdf', '.zip', '.tar', '.gz', '.exe', '.bin'}
            if file_ext in non_text_ext:
                path = os.path.splitext(path)[0] + '.txt'
            
            # Try to read old content
            old_content = None
            if self.project_manager:
                try:
                    old_content = self.project_manager.read_file(path)
                except Exception:
                    pass
            
            edit = FileEdit(
                edit_id=str(uuid.uuid4()),
                file_path=path,
                old_content=old_content,
                new_content=content,
                edit_type='create' if old_content is None else 'update',
                metadata={'source': 'update_block', 'raw_path': raw_path},
                enabled=True,
            )
            
            edits.append(edit)
        
        return edits
    
    def _parse_patch_blocks(self, response: str, active_file: str | None) -> list[FileEdit]:
        """Parse :::PATCH path::: with L##: directives.
        
        Format:
            :::PATCH path/to/file.py:::
            L10: old text => new text
            L20-L25: replacement content
            :::END:::
        
        Args:
            response: Response text
            active_file: Active file for path context
            
        Returns:
            List of FileEdit objects
        """
        # Fenced PATCH blocks
        fenced_pattern = r"```[a-z]*\s*\n\s*:::PATCH\s+([^\n:]+)\s*(?:::\s*)?\n((?:(?!:::END:::)[\s\S])*?)\s*:::END:::\s*\n```"
        fenced_matches = re.findall(fenced_pattern, response, re.DOTALL | re.IGNORECASE)
        
        # Remove fenced blocks to avoid double-parsing
        response_no_fenced = re.sub(fenced_pattern, '', response, flags=re.DOTALL | re.IGNORECASE)
        
        # Bare PATCH blocks - improved pattern to stop at first colon sequence
        bare_pattern = r":::PATCH\s+([^\n:]+?)\s*:::\s*\n(.*?)(?:\s*:::END:::)"
        bare_matches = re.findall(bare_pattern, response_no_fenced, re.DOTALL)
        
        all_matches = list(fenced_matches) + list(bare_matches)
        
        edits = []
        for raw_path, patch_body in all_matches:
            raw_path = raw_path.strip()
            path = self.path_resolver.normalize_path(raw_path, active_file)
            
            print(f"DEBUG: Parsing PATCH block - raw_path='{raw_path}', normalized='{path}'")
            
            # Apply patch to get new content
            success, new_content = self._apply_patch_body(path, patch_body)
            if not success or new_content is None:
                print(f"DEBUG: Failed to apply patch to {path}, skipping")
                continue
            
            # Check for non-text extensions
            file_ext = os.path.splitext(path)[1].lower()
            non_text_ext = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                           '.mp4', '.avi', '.mov', '.mp3', '.wav',
                           '.pdf', '.zip', '.tar', '.gz', '.exe', '.bin'}
            if file_ext in non_text_ext:
                path = os.path.splitext(path)[0] + '.txt'
            
            # Read old content
            old_content = None
            if self.project_manager:
                try:
                    old_content = self.project_manager.read_file(path)
                except Exception:
                    pass
            
            edit = FileEdit(
                edit_id=str(uuid.uuid4()),
                file_path=path,
                old_content=old_content,
                new_content=new_content,
                edit_type='update',
                metadata={'source': 'patch_block', 'raw_path': raw_path, 'patch_body': patch_body},
                enabled=True,
            )
            
            edits.append(edit)
        
        return edits
    
    def _parse_unified_diffs(self, response: str, active_file: str | None) -> list[FileEdit]:
        """Parse ```diff unified diff blocks.
        
        Format:
            ```diff
            --- a/file.py
            +++ b/file.py
            @@ -10,5 +10,5 @@
             context
            -old line
            +new line
            ```
        
        Args:
            response: Response text
            active_file: Active file for path context
            
        Returns:
            List of FileEdit objects
        """
        diff_pattern = r"```diff\s*\n(.*?)```"
        diff_blocks = re.findall(diff_pattern, response, re.DOTALL)
        
        edits = []
        for diff_text in diff_blocks:
            # Extract target path from diff headers
            target_path = self._extract_diff_target_path(diff_text)
            if not target_path:
                continue
            
            path = self.path_resolver.normalize_path(target_path, active_file)
            
            # Apply unified diff
            success, new_content = self._apply_unified_diff(path, diff_text)
            if not success or new_content is None:
                continue
            
            # Read old content
            old_content = None
            if self.project_manager:
                try:
                    old_content = self.project_manager.read_file(path)
                except Exception:
                    pass
            
            edit = FileEdit(
                edit_id=str(uuid.uuid4()),
                file_path=path,
                old_content=old_content,
                new_content=new_content,
                edit_type='update',
                metadata={'source': 'unified_diff', 'diff_text': diff_text},
                enabled=True,
            )
            
            edits.append(edit)
        
        return edits
    
    def _parse_fallback_code_blocks(self, response: str, active_file: str) -> list[FileEdit]:
        """Parse plain code blocks as full-file updates.
        
        Only used when no explicit edit markers are found and an active
        file is available for context.
        
        Args:
            response: Response text
            active_file: Active file path (required)
            
        Returns:
            List of FileEdit objects (usually 0 or 1)
        """
        if not active_file:
            return []
        
        code_block_pattern = r"```(?:markdown|md|text|python|py|javascript|js)?\s*\n(.*?)```"
        code_blocks = re.findall(code_block_pattern, response, re.DOTALL)
        
        if not code_blocks:
            return []
        
        # Use the first substantial code block
        for content in code_blocks:
            if len(content.strip()) > 20:  # Ignore trivial blocks
                # Read old content
                old_content = None
                if self.project_manager:
                    try:
                        old_content = self.project_manager.read_file(active_file)
                    except Exception:
                        pass
                
                edit = FileEdit(
                    edit_id=str(uuid.uuid4()),
                    file_path=active_file,
                    old_content=old_content,
                    new_content=content.strip(),
                    edit_type='update',
                    metadata={'source': 'code_block_fallback'},
                    enabled=True,
                )
                
                return [edit]
        
        return []
    
    def _apply_patch_body(self, file_path: str, patch_body: str) -> tuple[bool, str | None]:
        """Apply PATCH directives to file content.
        
        Supports:
        - L42: old => new (line replacement)
        - L10-L15: content (range replacement)
        - L42: content (insertion)
        
        Args:
            file_path: Path to file
            patch_body: PATCH block content with L##: directives
            
        Returns:
            Tuple of (success, new_content)
        """
        # Clean patch body (remove citations, footnotes)
        patch_body = self._clean_patch_body(patch_body)
        
        # Read current file
        if not self.project_manager:
            return False, None
        
        try:
            current = self.project_manager.read_file(file_path)
        except Exception as e:
            print(f"DEBUG: Failed to read file for patch {file_path}: {e}")
            return False, None
        
        if current is None:
            return False, None
        
        lines = current.split("\n")
        applied_any = False
        
        # Parse patch lines
        raw_lines = patch_body.splitlines()
        i = 0
        
        while i < len(raw_lines):
            raw = raw_lines[i]
            line = raw.strip()
            i += 1
            
            if not line:
                continue
            
            # Range replacement: L10-L15:
            m_range = re.match(r"L(\d+)\s*-\s*L(\d+):\s*(.*)", line)
            if m_range:
                start_no = int(m_range.group(1))
                end_no = int(m_range.group(2))
                trailing = m_range.group(3).strip()
                
                repl_lines = []
                if trailing:
                    repl_lines.append(trailing)
                
                # Capture subsequent lines
                while i < len(raw_lines):
                    peek = raw_lines[i]
                    if re.match(r"\s*L\d+:", peek):
                        break
                    repl_lines.append(peek)
                    i += 1
                
                # Apply replacement
                s_idx = max(1, start_no)
                e_idx = min(len(lines), end_no)
                
                if s_idx <= e_idx:
                    before = lines[:s_idx - 1]
                    after = lines[e_idx:]
                    lines = before + repl_lines + after
                    applied_any = True
                continue
            
            # Line replacement: L42: old => new
            m = re.match(r"L(\d+):\s*(.+?)\s*(?:=>|->)\s*(.+)", line)
            if m:
                line_no = int(m.group(1))
                old_text = m.group(2)
                new_text = m.group(3)
                
                if 1 <= line_no <= len(lines):
                    current_line = lines[line_no - 1]
                    if old_text in current_line:
                        lines[line_no - 1] = current_line.replace(old_text, new_text, 1)
                    else:
                        lines[line_no - 1] = new_text
                    applied_any = True
                continue
            
            # Simple replacement: L42: new text
            m2 = re.match(r"L(\d+):\s*(.*)", line)
            if m2:
                line_no = int(m2.group(1))
                first_line = m2.group(2).strip()
                
                new_lines = []
                if first_line:
                    new_lines.append(first_line)
                
                # Capture subsequent lines
                while i < len(raw_lines):
                    peek = raw_lines[i]
                    if re.match(r"\s*L\d+:", peek):
                        break
                    if re.match(r"\s*L\d+\s*-\s*L\d+:", peek):
                        break
                    new_lines.append(peek.rstrip())
                    i += 1
                
                # Insert at line_no
                if 1 <= line_no <= len(lines) + 1:
                    before = lines[:line_no - 1]
                    after = lines[line_no - 1:]
                    lines = before + new_lines + after
                    applied_any = True
        
        if not applied_any:
            return False, None
        
        new_content = "\n".join(lines)
        if current.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"
        
        return True, new_content
    
    def _apply_unified_diff(self, file_path: str, diff_text: str) -> tuple[bool, str | None]:
        """Apply unified diff to file content.
        
        Args:
            file_path: Path to file
            diff_text: Unified diff content
            
        Returns:
            Tuple of (success, new_content)
        """
        # Read original file
        if not self.project_manager:
            return False, None
        
        try:
            original = self.project_manager.read_file(file_path)
        except Exception as e:
            print(f"DEBUG: Failed to read file for diff {file_path}: {e}")
            return False, None
        
        if original is None:
            return False, None
        
        # Simple unified diff application (basic implementation)
        # TODO: Could use difflib.unified_diff or patch library for robustness
        orig_lines = original.split("\n")
        new_lines = []
        orig_idx = 0
        
        lines = diff_text.splitlines()
        i = 0
        
        # Skip headers
        while i < len(lines) and (lines[i].startswith('--- ') or lines[i].startswith('+++ ')):
            i += 1
        
        hunk_header_re = re.compile(r"@@\s*-([0-9]+)(?:,([0-9]+))?\s*\+([0-9]+)(?:,([0-9]+))?\s*@@")
        
        while i < len(lines):
            if not lines[i].startswith('@@'):
                i += 1
                continue
            
            m = hunk_header_re.match(lines[i])
            if not m:
                i += 1
                continue
            
            old_start = int(m.group(1)) - 1  # Convert to 0-based
            i += 1
            
            # Copy unchanged lines before hunk
            while orig_idx < old_start and orig_idx < len(orig_lines):
                new_lines.append(orig_lines[orig_idx])
                orig_idx += 1
            
            # Process hunk
            while i < len(lines) and not lines[i].startswith('@@'):
                if lines[i].startswith(' '):
                    # Context line
                    new_lines.append(lines[i][1:])
                    orig_idx += 1
                elif lines[i].startswith('+'):
                    # Addition
                    new_lines.append(lines[i][1:])
                elif lines[i].startswith('-'):
                    # Deletion
                    orig_idx += 1
                i += 1
        
        # Copy remaining lines
        while orig_idx < len(orig_lines):
            new_lines.append(orig_lines[orig_idx])
            orig_idx += 1
        
        new_content = "\n".join(new_lines)
        if original.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"
        
        return True, new_content
    
    def _extract_diff_target_path(self, diff_text: str) -> str | None:
        """Extract target file path from unified diff headers.
        
        Args:
            diff_text: Diff content
            
        Returns:
            File path or None
        """
        for line in diff_text.splitlines():
            if line.startswith('+++ '):
                p = line[4:].strip()
                if p.startswith('b/') or p.startswith('a/'):
                    p = p[2:]
                return p
        
        for line in diff_text.splitlines():
            if line.startswith('--- '):
                p = line[4:].strip()
                if p.startswith('b/') or p.startswith('a/'):
                    p = p[2:]
                return p
        
        return None
    
    def _clean_patch_body(self, patch_body: str) -> str:
        """Clean patch body by removing citations and footnotes.
        
        Args:
            patch_body: Raw patch content
            
        Returns:
            Cleaned patch body
        """
        # Remove Citations section
        citations_pattern = r'\*\*Citations:\*\*.*$'
        patch_body = re.sub(citations_pattern, '', patch_body, flags=re.DOTALL | re.MULTILINE)
        
        # Remove footnote markers
        footnote_pattern = r'\[\^\d+\]'
        patch_body = re.sub(footnote_pattern, '', patch_body)
        
        return patch_body.rstrip()
    
    def _deduplicate_edits(self, edits: list[FileEdit]) -> list[FileEdit]:
        """Remove duplicate edits (same path and content).
        
        Args:
            edits: List of potentially duplicate edits
            
        Returns:
            Deduplicated list
        """
        seen = set()
        unique = []
        
        for edit in edits:
            key = (edit.file_path, edit.new_content)
            if key not in seen:
                seen.add(key)
                unique.append(edit)
        
        return unique
    
    def _extract_summary(self, response: str) -> str | None:
        """Try to extract a summary from the response.
        
        Looks for phrases like "Here's what I changed:", "Summary:", etc.
        
        Args:
            response: Response text
            
        Returns:
            Extracted summary or None
        """
        # Look for common summary indicators
        summary_patterns = [
            r"(?:Here'?s? what I (?:changed|did|modified)):\s*([^\n]+)",
            r"(?:Summary|Changes):\s*([^\n]+)",
            r"(?:I'?ve? (?:made|applied|implemented)):\s*([^\n]+)",
        ]
        
        for pattern in summary_patterns:
            m = re.search(pattern, response, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        
        return None
