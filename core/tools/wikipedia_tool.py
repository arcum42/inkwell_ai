import requests
from core.tool_base import Tool


class WikiTool(Tool):
    """Tool for searching Wikipedia."""

    @property
    def name(self) -> str:
        return "WIKI"

    @property
    def description(self) -> str:
        return "Wikipedia: :::TOOL:WIKI:query...::: (Returns summary only. Use WEB_READ on the returned link for full details)"

    @property
    def requires_libraries(self) -> list:
        return ["requests"]

    def get_configurable_settings(self):
        """Return configurable settings for this tool."""
        return {
            "include_link": {"default": True, "type": "bool", "description": "Include Wikipedia link in response"},
        }

    def execute(self, query: str, settings=None):
        """Search Wikipedia.

        Args:
            query: Search query
            settings: Optional settings dict

        Returns:
            Tuple of (formatted_summary, None)
        """
        include_link = True
        if settings:
            include_link = settings.get("include_link", True)
        return (self.search(query, include_link=include_link), None)

    def search(self, query: str, include_link: bool = True) -> str:
        """Search Wikipedia for a topic.

        Args:
            query: Search query
            include_link: Whether to include Wikipedia link

        Returns:
            Formatted Wikipedia summary with optional link
        """
        try:
            headers = {'User-Agent': 'InkwellAI/1.0 (Educational Project)'}
            # First search for the page
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "opensearch",
                "search": query,
                "limit": 1,
                "namespace": 0,
                "format": "json"
            }
            response = requests.get(search_url, params=params, headers=headers)
            data = response.json()

            if not data[1]:
                return "No Wikipedia page found."

            title = data[1][0]

            # Now get summary
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
            response = requests.get(summary_url, headers=headers)
            summary_data = response.json()

            result = f"### {title}\n{summary_data.get('extract', 'No summary available.')}"
            if include_link:
                link = summary_data.get('content_urls', {}).get('desktop', {}).get('page', '')
                if link:
                    result += f"\n[Link]({link})"
            return result

        except Exception as e:
            return f"Error fetching Wikipedia: {e}"
