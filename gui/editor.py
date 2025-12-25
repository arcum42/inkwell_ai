"""
Backward compatibility wrapper for gui.editor module.

This module imports from the new gui.editors package structure
to maintain backward compatibility with existing code.
"""

# Import all classes from the new package structure
from gui.editors import (
    LinkDialog,
    CodeEditor,
    DocumentWidget,
    ImageViewerWidget,
    EditorWidget
)

__all__ = [
    'LinkDialog',
    'CodeEditor',
    'DocumentWidget',
    'ImageViewerWidget',
    'EditorWidget'
]
