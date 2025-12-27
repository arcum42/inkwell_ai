import pytest

from core.tool_base import get_registry
from core.tools.registry import clear_registry, register_default_tools, register_by_names


def test_preferred_schema_with_default_tools():
    # Ensure a clean registry and register all default tools
    clear_registry()
    register_default_tools()
    registry = get_registry()

    sid = registry.get_preferred_schema_id()
    assert sid == "tool_result"


def test_preferred_schema_with_only_image_gen():
    # Register only the GENERATE_IMAGE tool, which has no preferred schema
    clear_registry()
    register_by_names(["GENERATE_IMAGE"])  # replace registry with only this tool
    registry = get_registry()

    sid = registry.get_preferred_schema_id()
    assert sid is None


def test_preferred_schema_filter_enabled_names():
    # Register multiple tools, but filter to a subset where preferred schema exists
    clear_registry()
    register_default_tools()
    registry = get_registry()

    # Filtering to tools including SEARCH should still yield tool_result
    sid = registry.get_preferred_schema_id(enabled_names={"SEARCH"})
    assert sid == "tool_result"

    # Filtering to tools that have no preferred schema should yield None
    sid_none = registry.get_preferred_schema_id(enabled_names={"GENERATE_IMAGE"})
    assert sid_none is None
