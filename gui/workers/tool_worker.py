"""Worker thread for executing LLM tools."""

from PySide6.QtCore import QThread, Signal
from core.tool_base import get_registry


class ToolWorker(QThread):
    """Worker thread for executing LLM tools."""
    
    finished = Signal(str, object)  # result_text, extra_data (e.g. image results)

    def __init__(self, tool_name, query, enabled_tools=None, project_manager=None):
        super().__init__()
        self.tool_name = tool_name
        self.query = query
        self.enabled_tools = enabled_tools  # Optional set of allowed tool names
        self.project_manager = project_manager  # For accessing tool settings

    def run(self):
        """Execute the requested tool."""
        try:
            registry = get_registry()
            if self.enabled_tools is not None and self.tool_name not in self.enabled_tools:
                self.finished.emit(f"Error: Tool '{self.tool_name}' is disabled in this project", None)
                return
            tool = registry.get_tool(self.tool_name)
            
            if tool is None:
                self.finished.emit(f"Error: Unknown tool '{self.tool_name}'", None)
                return
            
            if not tool.is_available():
                self.finished.emit(f"Error: Tool '{self.tool_name}' is not available (missing dependencies)", None)
                return
            
            # Get tool settings from project config
            settings = None
            if self.project_manager:
                settings = self.project_manager.get_tool_settings(self.tool_name)
            
            # Execute the tool with settings
            result_text, extra_data = tool.execute(self.query, settings=settings)
            self.finished.emit(result_text, extra_data)
            
        except Exception as e:
            self.finished.emit(f"Tool Error: {e}", None)
