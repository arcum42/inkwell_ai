import requests
import bs4
from core.tool_base import Tool, get_registry

try:
    from ddgs import DDGS
    HAS_DDG = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDG = True
    except ImportError:
        HAS_DDG = False


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
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = bs4.BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
                
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text[:max_length] # Limit length
        except Exception as e:
            return f"Error reading URL: {e}"


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
        return HAS_DDG
    
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
        if not HAS_DDG:
            return "Error: duckduckgo-search library not installed. Keep this in mind."
        
        try:
            results = DDGS().text(query, max_results=max_results)
            if not results:
                return "No search results found."
                
            # Format results
            formatted = ""
            for r in results:
                formatted += f"- [{r['title']}]({r['href']}): {r['body']}\n"
            return formatted
        except Exception as e:
            return f"Error searching: {e}"


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
        return HAS_DDG
    
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
        if not HAS_DDG:
            return ("Error: duckduckgo-search library not installed.", None)
            
        try:
            results = DDGS().images(query, max_results=max_images)
            if not results:
                return ("No images found.", None)
            # Return structured result
            result_text = f"Found {len(results)} images. Asking user to select..."
            return (result_text, results)
        except Exception as e:
            return (f"Error searching images: {e}", None)


# Register all tools on module import
def _register_default_tools():
    """Register all default tools in the registry."""
    registry = get_registry()
    registry.register(WebReader())
    registry.register(WebSearcher())
    registry.register(WikiTool())
    registry.register(ImageSearcher())


# Auto-register on import
_register_default_tools()
