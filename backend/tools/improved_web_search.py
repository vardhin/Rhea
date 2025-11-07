from tool_server import tool
import requests
from bs4 import BeautifulSoup

@tool(name="improved_web_search", category="web", tags=["search", "internet", "news"], requirements=["requests","bs4"])
def improved_web_search(query: str, num_results: int = 5) -> dict:
    """Search the web for information, with improved robustness.
    
    Args:
        query: Search query
        num_results: Number of results to return
    
    Returns:
        Search results with titles and snippets
    """
    # Using DuckDuckGo HTML scraping as a default, with a timeout
    try:
        url = f"https://html.duckduckgo.com/html/?q={query}"
        response = requests.get(url, timeout=10) # Added a timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        for result in soup.find_all('div', class_='result')[:num_results]:
            title_tag = result.find('a', class_='result__a')
            snippet_tag = result.find('a', class_='result__snippet')
            if title_tag and snippet_tag:
                results.append({
                    'title': title_tag.get_text(),
                    'snippet': snippet_tag.get_text(),
                    'url': title_tag.get('href')
                })
        
        return {'results': results, 'count': len(results), 'status': 'success'}
    except requests.exceptions.Timeout:
        return {'error': 'Request timed out while searching the web.', 'status': 'failure'}
    except requests.exceptions.RequestException as e:
        return {'error': f'An error occurred during web search: {e}', 'status': 'failure'}
    except Exception as e:
        return {'error': f'An unexpected error occurred: {e}', 'status': 'failure'}