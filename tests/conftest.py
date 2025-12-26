"""Pytest configuration to ensure imports from the project root work.

This adds the repository root to `sys.path` so tests can import top-level
modules like `core.*` regardless of the current working directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Resolve repository root (one level above the tests directory)
REPO_ROOT = Path(__file__).resolve().parents[1]
root_str = str(REPO_ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
