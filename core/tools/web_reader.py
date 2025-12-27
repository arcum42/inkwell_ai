from core.tool_base import Tool
from .util import read_and_clean_url


class WebReader(Tool):
    """Tool for reading content from web pages."""

    @property
    def name(self) -> str:
        return "WEB_READ"

    @property
    def description(self) -> str:
        return "Read Web Page: :::TOOL:WEB_READ:https://url...::: (Use this for full article content)"

    @property
    def requires_libraries(self) -> list:
        return ["requests", "bs4"]

    def get_configurable_settings(self):
        """Return configurable settings for this tool."""
        return {
            "max_length": {"default": 10000, "type": "int", "description": "Maximum characters to return"},
        }

    def get_preferred_schema_id(self):
        """Suggest structured schema for page content results."""
        return "tool_result"

    def execute(self, query: str, settings=None):
        """Read content from a web page.

        Args:
            query: URL to read
            settings: Optional settings dict

        Returns:
            Tuple of (text_content, None)
        """
        max_length = 10000
        if settings:
            max_length = settings.get("max_length", 10000)
        return (self.read(url=query, max_length=max_length), None)

    def read(self, url: str, max_length: int = 10000) -> str:
        """Read and extract text from a URL.

        Args:
            url: URL to read
            max_length: Maximum characters to return

        Returns:
            Extracted text content
        """
        return read_and_clean_url(url, max_length=max_length)
