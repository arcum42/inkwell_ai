import requests
import bs4
try:
    from ddgs import DDGS
    HAS_DDG = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDG = True
    except ImportError:
        HAS_DDG = False

class WebReader:
    def read(self, url):
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

class WebSearcher:
    def search(self, query):
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

class WikiTool:
    def search(self, query):
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

class ImageSearcher:
    def search(self, query):
        if not HAS_DDG:
            return "Error: duckduckgo-search library not installed."
            
        try:
            results = DDGS().images(query, max_results=10)
            if not results:
                return "No images found."
            # Return list of dicts
            return results
        except Exception as e:
            return f"Error searching images: {e}"
