from core.tool_base import Tool
from .util import ddg_available, ddg_text


class WebSearcher(Tool):
    """Tool for searching the web using DuckDuckGo."""

    @property
    def name(self) -> str:
        return "SEARCH"

    @property
    def description(self) -> str:
        return "Web Search: :::TOOL:SEARCH:query...:::"

    @property
    def requires_libraries(self) -> list:
        return ["duckduckgo_search"]

    def is_available(self) -> bool:
        """Check if DuckDuckGo search is available."""
        return ddg_available()

    def execute(self, query: str, settings=None):
        """Search the web.

        Args:
            query: Search query string
            settings: Optional settings dict

        Returns:
            Tuple of (formatted_results, None)
        """
        max_results = 5
        if settings:
            max_results = settings.get("max_results", 5)
        return (self.search(query, max_results=max_results), None)

    def search(self, query: str, max_results: int = 5) -> str:
        """Perform a web search.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Formatted search results
        """
        if not ddg_available():
            return "Error: duckduckgo-search library not installed. Keep this in mind."
        results = ddg_text(query, max_results=max_results)
        if not results:
            return "No search results found."
        # Format results
        formatted = ""
        for r in results:
            try:
                title = r.get('title')
                href = r.get('href')
                body = r.get('body')
                formatted += f"- [{title}]({href}): {body}\n"
            except Exception:
                continue
        return formatted or "No search results found."
