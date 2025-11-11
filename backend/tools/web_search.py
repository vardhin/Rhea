from tool_server import tool
import requests
from bs4 import BeautifulSoup

@tool(name="web_search", category="web", tags=["search", "internet"], requirements=["requests", "beautifulsoup4"])
def web_search(query: str, num_results: int = 5) -> dict:
    """Search the web for information using DuckDuckGo.
    
    Args:
        query: Search query string
        num_results: Number of results to return (default: 5)
    
    Returns:
        Dictionary with search results: {"results": [...], "count": int}
    
    Raises:
        ValueError: If query is empty
        RuntimeError: If search fails or returns no results
    """
    # Validate input
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")
    
    if num_results < 1 or num_results > 20:
        raise ValueError("num_results must be between 1 and 20")
    
    try:
        # Perform search
        url = f"https://html.duckduckgo.com/html/?q={query}"
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        # Parse results
        soup = BeautifulSoup(response.text, 'html.parser')
        result_divs = soup.find_all('div', class_='result')
        
        if not result_divs:
            raise RuntimeError(f"No search results found for query: {query}")
        
        results = []
        for result in result_divs[:num_results]:
            title_elem = result.find('a', class_='result__a')
            snippet_elem = result.find('a', class_='result__snippet')
            
            if title_elem:
                results.append({
                    'title': title_elem.get_text(strip=True),
                    'snippet': snippet_elem.get_text(strip=True) if snippet_elem else '',
                    'url': title_elem.get('href', '')
                })
        
        if not results:
            raise RuntimeError(f"Failed to parse search results for query: {query}")
        
        return {'results': results, 'count': len(results)}
        
    except requests.Timeout:
        raise RuntimeError(f"Search request timed out for query: {query}")
    except requests.RequestException as e:
        raise RuntimeError(f"Network error during search: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Web search failed: {str(e)}")