from core.tool_base import Tool
from .util import ddg_available, ddg_images


class ImageSearcher(Tool):
    """Tool for searching images using DuckDuckGo."""

    @property
    def name(self) -> str:
        return "IMAGE"

    @property
    def description(self) -> str:
        return "Image Search: :::TOOL:IMAGE:query...:::"

    @property
    def requires_libraries(self) -> list:
        return ["duckduckgo_search"]

    def get_configurable_settings(self):
        """Return configurable settings for this tool."""
        return {
            "max_images": {"default": 10, "type": "int", "description": "Maximum images to return"},
        }

    def is_available(self) -> bool:
        """Check if DuckDuckGo search is available."""
        return ddg_available()

    def execute(self, query: str, settings=None):
        """Search for images.

        Args:
            query: Search query
            settings: Optional settings dict

        Returns:
            Tuple of (result_message, image_results)
            - result_message: String describing results
            - image_results: List of image dicts or None if error
        """
        max_images = 10
        if settings:
            max_images = settings.get("max_images", 10)
        return self.search(query, max_images=max_images)

    def search(self, query: str, max_images: int = 10):
        """Search for images.

        Args:
            query: Search query
            max_images: Maximum number of images to return

        Returns:
            Tuple of (result_text, extra_data) where extra_data is list of image results
        """
        if not ddg_available():
            return ("Error: duckduckgo-search library not installed.", None)
        results = ddg_images(query, max_results=max_images)
        if not results:
            return ("No images found.", None)
        # Return structured result
        result_text = f"Found {len(results)} images. Asking user to select..."
        return (result_text, results)
