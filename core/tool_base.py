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

    def has_dialog(self) -> bool:
        """Return whether this tool has a UI dialog for direct invocation.
        
        Override to return True if the tool should appear in the Tools menu.
        Default: False
        """
        return False
    
    def show_dialog(self, parent=None) -> Optional[Tuple[str, Optional[Any]]]:
        """Show a UI dialog for this tool and return (query, extra_data) or None if cancelled.
        
        Args:
            parent: Parent widget for the dialog
            
        Returns:
            Tuple of (query_string, None) if user confirms, or None if cancelled.
            The query string will be passed to execute().
        """
        return None

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
            "## Available Tools - YOU MUST USE THESE FOR SEARCHES AND IMAGE REQUESTS",
            "You have access to external tools. When the user asks you to search, find information, or retrieve images, you MUST use these tools:",
            ""
        ]
        for i, tool in enumerate(tools, 1):
            lines.append(f"{i}. {tool.description}")
            lines.append(f"   Usage: {tool.get_usage_pattern()}")
        lines.append("")
        lines.append("CRITICAL: When a user requests a search or image lookup:")
        lines.append("1. Identify WHICH SERVICE they want")
        lines.append("2. Use ONLY the matching tool for that service")
        lines.append("3. DO NOT try to provide the information yourself")
        lines.append("4. DO NOT return JSON or structured data")
        lines.append("5. IMMEDIATELY output ONLY the tool command on its own line")
        lines.append("6. Use format: :::TOOL:SERVICENAME:query:::") 
        lines.append("7. Do not wrap in code blocks, markdown, or add any other text")
        lines.append("")
        lines.append("SERVICE SELECTION GUIDE (EXPLICIT REQUESTS ONLY):")
        lines.append("Only use these tools when user EXPLICITLY asks to SEARCH, FIND, or SHOW images/information:")
        lines.append("")
        lines.append("EXPLICIT IMAGE SEARCH REQUESTS:")
        lines.append("- User says 'Find pony images', 'Search for pony pictures', 'Show me pony' → Use DERPIBOORU")
        lines.append("- User says 'Find AI pony', 'Show AI generated pony' → Use TANTABUS")  
        lines.append("- User says 'Find furry', 'Search e621' → Use E621")
        lines.append("- User says 'Find images', 'Show pictures' (general) → Use IMAGE")
        lines.append("")
        lines.append("EXPLICIT INFORMATION REQUESTS:")
        lines.append("- User says 'Search the web for...', 'Look up...', 'Find information about...' → Use SEARCH")
        lines.append("- User says 'What is...', 'Tell me about...' (wiki) → Use WIKI")
        lines.append("- User says 'Read this website', 'Get content from...' → Use WEB_READ")
        lines.append("- User says 'Generate an image' → Use GENERATE_IMAGE")
        lines.append("")
        lines.append("IMPORTANT - DO NOT USE TOOLS FOR:")
        lines.append("- Casual mentions or discussions about ponies/topics (not a search request)")
        lines.append("- Formatting questions or document editing (not an image search)")
        lines.append("- Context or reference material the user is providing (they're informing, not requesting)")
        lines.append("")
        lines.append("Examples:")
        lines.append("- User: 'Find pony images for reference' → Use DERPIBOORU")
        lines.append("- User: 'Show me AI pony pictures' → Use TANTABUS")
        lines.append("- User: 'Edit this file about ponies' → DO NOT use tools (editing request, not image search)")
        lines.append("- User: 'My story involves ponies' → DO NOT use tools (contextual info, not a search)")
        lines.append("- User: 'Search the web for pony anatomy' → Use SEARCH (web info, not images)")
        lines.append("- User: 'Look up what Derpibooru is' → Use WIKI")
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
