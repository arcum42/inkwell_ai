"""Image Generation Tool for ComfyUI integration."""

from typing import Tuple, Optional, Any
from core.tool_base import Tool


class ImageGenTool(Tool):
    @property
    def name(self) -> str:
        return "GENERATE_IMAGE"
    
    @property
    def description(self) -> str:
        return "Generate Image: :::GENERATE_IMAGE:::\\nPrompt: description...\\n:::END::: (Uses ComfyUI to create images)"
    
    @property
    def requires_libraries(self) -> list:
        # ComfyUI is optional; doesn't require Python packages
        return []
    
    def execute(self, query: str, settings: Optional[dict] = None) -> Tuple[str, Optional[Any]]:
        """This tool doesn't execute directly - it's parsed in main_window.
        
        Image generation is handled by the main window's response parser
        which extracts :::GENERATE_IMAGE::: blocks and invokes ComfyUI.
        This Tool class exists for documentation and settings UI only.
        """
        return "Image generation handled by main window parser", None
    
    def is_available(self) -> bool:
        """Always available (ComfyUI availability checked at generation time)."""
        return True
