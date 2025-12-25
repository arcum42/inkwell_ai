"""Backward compatibility wrapper for the legacy gui.workers module.

Worker implementations have been moved into the gui.workers package.
This module re-exports the worker classes to maintain backward compatibility:

    from gui.workers import ChatWorker, ToolWorker, BatchWorker, IndexWorker

New code should import from gui.workers package directly.
"""

from gui.workers import (
    ChatWorker,
    ToolWorker,
    BatchWorker,
    IndexWorker,
)

__all__ = [
    "ChatWorker",
    "ToolWorker",
    "BatchWorker",
    "IndexWorker",
]
