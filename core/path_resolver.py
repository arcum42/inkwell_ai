"""Path normalization and resolution for file edits.

Centralizes all path handling logic to ensure consistent behavior
across different edit formats and sources.
"""

import os
import re
from pathlib import Path


class PathResolver:
    """Centralized path normalization and resolution service.
    
    Handles:
    - Removing quotes, backticks, angle brackets
    - Normalizing slashes and relative paths
    - Resolving basenames to full project paths
    - Converting absolute paths to project-relative
    """
    
    def __init__(self, project_root: str):
        """Initialize resolver with project root.
        
        Args:
            project_root: Absolute path to project root directory
        """
        self.project_root = os.path.abspath(project_root)
        self._file_index: dict[str, list[str]] = {}
        self._refresh_index()
    
    def normalize_path(self, raw_path: str, active_file: str | None = None) -> str:
        """Normalize and resolve a path from LLM output.
        
        Handles various formats and edge cases:
        - Quoted paths: "file.md", 'file.md'
        - Backticks: `file.md`
        - Angle brackets: <file.md>
        - Relative paths: ./file.md, ../file.md
        - Absolute paths within project
        - Bare filenames (resolved via index)
        - Fallback to active file when empty
        
        Args:
            raw_path: Raw path string from LLM
            active_file: Currently active file path (for fallback/context)
            
        Returns:
            Normalized path relative to project root
        """
        path = raw_path.strip()
        
        # Remove enclosing quotes/backticks/angle brackets
        if len(path) >= 2:
            if (path.startswith('"') and path.endswith('"')) or \
               (path.startswith("'") and path.endswith("'")):
                path = path[1:-1]
            elif (path.startswith('<') and path.endswith('>')) or \
                 (path.startswith('`') and path.endswith('`')):
                path = path[1:-1]
        
        # Normalize slashes
        path = path.replace('\\', '/')
        
        # Remove leading './'
        if path.startswith('./'):
            path = path[2:]
        
        # Handle line markers that got attached (e.g., "file.md L12:")
        if '\n' in path:
            path = path.splitlines()[0].strip()
        
        # Remove line markers like " L12:"
        path = re.split(r"\s+L\d+:", path)[0].strip()
        
        # Remove stray block terminators
        for marker in (":::END:::", ":::END", ":::"):
            if marker in path:
                path = path.split(marker)[0].strip()
        
        # Collapse duplicate slashes (preserve single leading '/')
        while '//' in path:
            path = path.replace('//', '/')
        
        path = path.strip()
        
        # If empty, fallback to active file
        if not path and active_file:
            return active_file
        
        if not path:
            return "untitled.txt"
        
        # Convert absolute path to relative if within project
        if os.path.isabs(path):
            try:
                rel = os.path.relpath(path, self.project_root)
                if not rel.startswith('..'):
                    path = rel
            except (ValueError, Exception):
                # Different drives on Windows, etc.
                pass
        
        # If no directory separator (basename only), try to resolve
        if '/' not in path:
            resolved = self.resolve_basename(path, active_file)
            if resolved:
                return resolved
        
        # Final cleanup
        path = path.strip('/')
        return path
    
    def resolve_basename(self, basename: str, active_file: str | None = None) -> str | None:
        """Resolve a bare filename to full project-relative path.
        
        Strategy:
        1. Look up in file index
        2. If single match, return it
        3. If multiple matches and active_file provided, prefer same directory
        4. Otherwise return first match or None
        
        Args:
            basename: Bare filename without path
            active_file: Currently active file (for directory preference)
            
        Returns:
            Resolved path or None if not found
        """
        candidates = self._file_index.get(basename, [])
        
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Multiple candidates - prefer same directory as active file
        if active_file:
            active_dir = os.path.dirname(active_file)
            for candidate in candidates:
                if os.path.dirname(candidate) == active_dir:
                    return candidate
        
        # Return first match as fallback
        return candidates[0]
    
    def _refresh_index(self):
        """Build index of all files in project for fast basename lookup.
        
        Creates a mapping of basename -> [relative_paths] for all files
        in the project directory.
        """
        self._file_index.clear()
        
        if not os.path.isdir(self.project_root):
            return
        
        # Walk project directory
        for root, dirs, files in os.walk(self.project_root):
            # Skip common ignore directories
            dirs[:] = [d for d in dirs if d not in {
                '.git', '.venv', 'venv', '__pycache__', 'node_modules',
                '.pytest_cache', '.mypy_cache', 'build', 'dist'
            }]
            
            for filename in files:
                # Skip hidden files and certain extensions
                if filename.startswith('.'):
                    continue
                    
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, self.project_root)
                
                # Normalize slashes
                relative_path = relative_path.replace('\\', '/')
                
                # Add to index
                if filename not in self._file_index:
                    self._file_index[filename] = []
                self._file_index[filename].append(relative_path)
    
    def refresh_index(self):
        """Public method to refresh the file index.
        
        Call this when files are added/removed from the project.
        """
        self._refresh_index()
    
    def get_absolute_path(self, relative_path: str) -> str:
        """Convert project-relative path to absolute path.
        
        Args:
            relative_path: Path relative to project root
            
        Returns:
            Absolute path
        """
        return os.path.join(self.project_root, relative_path)
    
    def is_in_project(self, path: str) -> bool:
        """Check if a path is within the project directory.
        
        Args:
            path: Path to check (absolute or relative)
            
        Returns:
            True if path is inside project
        """
        if not os.path.isabs(path):
            path = self.get_absolute_path(path)
        
        try:
            rel = os.path.relpath(path, self.project_root)
            return not rel.startswith('..')
        except (ValueError, Exception):
            return False
