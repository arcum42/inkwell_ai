"""Helper utilities for tool registration and discovery."""

from typing import Iterable, Optional, Dict, Type

from core.tool_base import get_registry, Tool
from .web_reader import WebReader
from .web_search import WebSearcher
from .wikipedia_tool import WikiTool
from .image_search import ImageSearcher

# Map of tool names to their classes for conditional registration
AVAILABLE_TOOLS: Dict[str, Type[Tool]] = {
    "WEB_READ": WebReader,
    "SEARCH": WebSearcher,
    "WIKI": WikiTool,
    "IMAGE": ImageSearcher,
}


def clear_registry() -> None:
    """Remove all registered tools from the global registry.
    Useful for tests or dynamic reloads.
    """
    registry = get_registry()
    for tool in list(registry.get_all_tools()):
        registry.unregister(tool.name)


def register_default_tools(enabled: Optional[Iterable[str]] = None) -> None:
    """Register default tools, optionally filtered by name.

    Args:
        enabled: Optional iterable of tool names to register. If None, registers all.
    """
    registry = get_registry()
    names = set(enabled) if enabled is not None else set(AVAILABLE_TOOLS.keys())
    for name in names:
        cls = AVAILABLE_TOOLS.get(name)
        if cls is None:
            continue
        try:
            registry.register(cls())
        except Exception:
            # Skip tools that fail to construct
            continue


def list_registered_tool_names() -> list:
    """Return a list of currently registered tool names."""
    registry = get_registry()
    return [t.name for t in registry.get_all_tools()]


def register_by_names(names: Iterable[str]) -> None:
    """Register tools by a given list of names, replacing any existing tools."""
    clear_registry()
    register_default_tools(enabled=names)
