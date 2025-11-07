from tool_server import tool
import requests
from bs4 import BeautifulSoup

@tool(name="web_search", category="web", tags=["search", "internet", "news"], requirements=["requests","bs4"])
def web_search(query: str, num_results: int = 5) -> dict:
    """Search the web for information.
    
    Args:
        query: Search query
        num_results: Number of results to return
    
    Returns:
        Search results with titles, snippets, and URLs
    """
    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        for result in soup.find_all('div', class_='result')[:num_results]:
            title_tag = result.find('a', class_='result__a')
            snippet_tag = result.find('a', class_='result__snippet')
            
            if title_tag and snippet_tag:
                title = title_tag.get_text()
                snippet = snippet_tag.get_text()
                link = title_tag.get('href')
                results.append({
                    'title': title,
                    'snippet': snippet,
                    'url': link
                })
        
        return {'results': results, 'count': len(results)}
    except requests.exceptions.RequestException as e:
        return {'error': f'Request failed: {e}'}
    except Exception as e:
        return {'error': f'An unexpected error occurred: {e}'}