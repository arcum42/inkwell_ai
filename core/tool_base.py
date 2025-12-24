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
    
    @abstractmethod
    def execute(self, query: str) -> Tuple[str, Optional[Any]]:
        """Execute the tool with the given query.
        
        Args:
            query: The query string from the LLM
            
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
    
    def get_available_tools(self) -> list:
        """Get list of available (usable) tools.
        
        Returns:
            List of Tool instances that are currently available
        """
        return [t for t in self._tools.values() if t.is_available()]
    
    def get_all_tools(self) -> list:
        """Get all registered tools regardless of availability.
        
        Returns:
            List of all Tool instances
        """
        return list(self._tools.values())
    
    def get_tool_instructions(self) -> str:
        """Generate tool instructions for LLM context.
        
        Returns:
            Formatted string describing available tools and their usage
        """
        tools = self.get_available_tools()
        if not tools:
            return ""
        
        lines = ["You have access to the following tools:"]
        for i, tool in enumerate(tools, 1):
            lines.append(f"{i}. {tool.description}")
            lines.append(f"   Usage: {tool.get_usage_pattern()}")
        lines.append("Use these formats to request information or images. Stop generating after the tool command.")
        return "\n".join(lines)


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry.
    
    Returns:
        The global ToolRegistry instance
    """
    return _registry
