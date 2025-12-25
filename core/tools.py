"""Backward compatibility wrapper for the legacy core.tools module.

The tool implementations have been moved into the package core.tools.
This module re-exports the tool classes and preserves the previous
auto-registration behavior so existing imports continue to work:

    from core.tools import WebReader, WebSearcher, WikiTool, ImageSearcher

New code should import from the package modules or core.tools package directly.
"""

from core.tools import (
    WebReader,
    WebSearcher,
    WikiTool,
    ImageSearcher,
    register_default_tools as _register_default_tools,
)

# Preserve previous side-effect: register tools on import
_register_default_tools()
