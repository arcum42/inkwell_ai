"""Base classes for LLM tool system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


class Tool(ABC):
    """Base class for LLM tools.
    
    All tools must inherit from this class and implement the required methods.
    Tools are registered in the global registry and can be invoked by the LLM
    using the pattern: :::TOOL:NAME:query:::
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier (e.g., 'WEB_READ', 'SEARCH')."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM context (e.g., 'Read Web Page: ...')."""
        pass
    
    @property
    def requires_libraries(self) -> list:
        """Optional dependencies required for this tool.
        
        Returns:
            List of library names (e.g., ['requests', 'beautifulsoup4'])
        """
        return []
    
    def get_configurable_settings(self) -> Dict[str, Any]:
        """Return dict of setting names to default values for this tool.
        
        Override this to define configurable settings. Format:
        {
            "setting_name": {"default": value, "type": "int"|"str"|"bool", "description": "..."},
            ...
        }
        
        Returns:
            Dict of setting schemas
        """
        return {}
    
    @abstractmethod
    def execute(self, query: str, settings: Optional[Dict[str, Any]] = None) -> Tuple[str, Optional[Any]]:
        """Execute the tool with the given query.
        
        Args:
            query: The query string from the LLM
            settings: Optional dict of settings from project config
            
        Returns:
            Tuple of (result_text, extra_data)
            - result_text: String result to feed back to LLM
            - extra_data: Optional structured data (e.g., list of image results)
        """
        pass
    
    def is_available(self) -> bool:
        """Check if tool can be used (dependencies installed, etc.).
        
        Returns:
            True if tool is available, False otherwise
        """
        # Check if required libraries are importable
        for lib in self.requires_libraries:
            try:
                __import__(lib)
            except ImportError:
                return False
        return True
    
    def get_usage_pattern(self) -> str:
        """Return the invocation pattern for LLM.
        
        Returns:
            String like ":::TOOL:NAME:query...:::"
        """
        return f":::TOOL:{self.name}:query...:::"

    def get_preferred_schema_id(self) -> Optional[str]:
        """Return a preferred structured schema id for this tool, if any.

        Tools can override to guide structured response selection per-request.
        Example: return 'tool_result' for data-fetching tools.
        Default: None.
        """
        return None


class ToolRegistry:
    """Central registry for all available tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """Register a tool.
        
        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool
    
    def unregister(self, name: str):
        """Remove a tool from registry.
        
        Args:
            name: Name of tool to remove
        """
        if name in self._tools:
            del self._tools[name]
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name.
        
        Args:
            name: Tool name to look up
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def get_available_tools(self, enabled_names: Optional[set] = None) -> list:
        """Get list of available (usable) tools.
        
        Args:
            enabled_names: Optional set of tool names to allow. If None, all registered tools are considered.
        
        Returns:
            List of Tool instances that are currently available and permitted
        """
        tools = self._tools.values()
        if enabled_names is not None:
            tools = [t for t in tools if t.name in enabled_names]
        return [t for t in tools if t.is_available()]
    
    def get_all_tools(self) -> list:
        """Get all registered tools regardless of availability.
        
        Returns:
            List of all Tool instances
        """
        return list(self._tools.values())
    
    def get_tool_instructions(self, enabled_names: Optional[set] = None) -> str:
        """Generate tool instructions for LLM context.
        
        Args:
            enabled_names: Optional set of tool names permitted for this project
        
        Returns:
            Formatted string describing available tools and their usage
        """
        tools = self.get_available_tools(enabled_names)
        if not tools:
            return ""
        
        lines = [
            "## Available Tools",
            "You have access to external tools. When the user asks you to search, find information, or retrieve images, use these tools:",
            ""
        ]
        for i, tool in enumerate(tools, 1):
            lines.append(f"{i}. {tool.description}")
            lines.append(f"   Usage: {tool.get_usage_pattern()}")
        lines.append("")
        lines.append("IMPORTANT: To use a tool, output ONLY the tool command on its own line. Do not wrap it in code blocks or add extra text on the same line. Stop generating immediately after the tool command.")
        lines.append("")
        lines.append("Examples:")
        lines.append("- User: 'Find an image of a cat' → You: :::TOOL:IMAGE:cat:::")
        lines.append("- User: 'Search for python tutorials' → You: :::TOOL:SEARCH:python tutorials:::")
        lines.append("- User: 'What is quantum computing' → You: :::TOOL:WIKI:quantum computing:::")
        return "\n".join(lines)

    def get_preferred_schema_id(self, enabled_names: Optional[set] = None) -> Optional[str]:
        """Return the first preferred schema id from available tools.

        Args:
            enabled_names: Optional set of tool names allowed.
        Returns:
            A schema id string or None.
        """
        for tool in self.get_available_tools(enabled_names):
            sid = None
            try:
                sid = tool.get_preferred_schema_id()
            except Exception:
                sid = None
            if sid:
                return sid
        return None


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry.
    
    Returns:
        The global ToolRegistry instance
    """
    return _registry
