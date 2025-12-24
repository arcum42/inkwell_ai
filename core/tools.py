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
    
    def execute(self, query: str):
        """Read content from a web page.
        
        Args:
            query: URL to read
            
        Returns:
            Tuple of (text_content, None)
        """
        return (self.read(query), None)
    
    def read(self, url: str) -> str:
        """Read and extract text from a URL.
        
        Args:
            url: URL to read
            
        Returns:
            Extracted text content (up to 10000 chars)
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
            
            return text[:10000] # Limit length
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
    
    def execute(self, query: str):
        """Search the web.
        
        Args:
            query: Search query string
            
        Returns:
            Tuple of (formatted_results, None)
        """
        return (self.search(query), None)
    
    def search(self, query: str) -> str:
        """Perform a web search.
        
        Args:
            query: Search query
            
        Returns:
            Formatted search results
        """
        if not HAS_DDG:
            return "Error: duckduckgo-search library not installed. Keep this in mind."
        
        try:
            results = DDGS().text(query, max_results=5)
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
    
    def execute(self, query: str):
        """Search Wikipedia.
        
        Args:
            query: Search query
            
        Returns:
            Tuple of (formatted_summary, None)
        """
        return (self.search(query), None)
    
    def search(self, query: str) -> str:
        """Search Wikipedia for a topic.
        
        Args:
            query: Search query
            
        Returns:
            Formatted Wikipedia summary with link
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
            
            return f"### {title}\n{summary_data.get('extract', 'No summary available.')}\n[Link]({summary_data.get('content_urls', {}).get('desktop', {}).get('page', '')})"
            
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
    
    def is_available(self) -> bool:
        """Check if DuckDuckGo search is available."""
        return HAS_DDG
    
    def execute(self, query: str):
        """Search for images.
        
        Args:
            query: Search query
            
        Returns:
            Tuple of (result_message, image_results)
            - result_message: String describing results
            - image_results: List of image dicts or None if error
        """
        return self.search(query)
    
    def search(self, query: str):
        """Search for images.
        
        Args:
            query: Search query
            
        Returns:
            Tuple of (result_text, extra_data) where extra_data is list of image results
        """
        if not HAS_DDG:
            return ("Error: duckduckgo-search library not installed.", None)
            
        try:
            results = DDGS().images(query, max_results=10)
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
