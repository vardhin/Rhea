from flask import Flask, request, jsonify
from functools import wraps
import requests
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
import re
import json
from pathlib import Path

# Import gemini module functions
from gemini_module import (
    set_api_key,
    send_message_to_gemini_model,
    get_current_parameters,
    set_parameters,
    set_thinking_mode,
    get_full_config
)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('TOOL_USER_SECRET', 'tool-user-secret-key')

# Tool Server Configuration
TOOL_SERVER_URL = os.getenv('TOOL_SERVER_URL', 'http://localhost:5001')
TOOL_SERVER_USERNAME = os.getenv('TOOL_SERVER_USERNAME', 'admin')
TOOL_SERVER_PASSWORD = os.getenv('TOOL_SERVER_PASSWORD', 'admin123')

# Gemini Configuration
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')

# Load all available Gemini API keys
GEMINI_API_KEYS = []
for i in range(1, 9):  # Keys 1 through 8
    key = os.getenv(f'GEMINI_API_KEY_{i}')
    if key:
        GEMINI_API_KEYS.append(key)

# Track current key index
_current_key_index = 0
_key_lock = None  # Will be initialized with threading.Lock()

# Initialize Gemini with first available key
if GEMINI_API_KEYS:
    set_api_key(GEMINI_API_KEYS[0])
    logger.info(f"✓ Loaded {len(GEMINI_API_KEYS)} Gemini API key(s)")
    logger.info(f"✓ Using API key 1/{len(GEMINI_API_KEYS)}")
    
    # Initialize lock for thread-safe key rotation
    import threading
    _key_lock = threading.Lock()
else:
    logger.warning("⚠ No Gemini API keys found in environment")

# Tool Server Authentication Token Cache
_tool_server_token = None
_token_expiry = None

def get_next_gemini_key():
    """Get the next Gemini API key in round-robin fashion"""
    global _current_key_index
    
    if not GEMINI_API_KEYS:
        return None
    
    with _key_lock:
        # Move to next key
        _current_key_index = (_current_key_index + 1) % len(GEMINI_API_KEYS)
        next_key = GEMINI_API_KEYS[_current_key_index]
        
        # Update gemini_module with new key
        set_api_key(next_key)
        
        logger.info(f"🔄 Rotated to API key {_current_key_index + 1}/{len(GEMINI_API_KEYS)}")
        return next_key

def get_current_key_info():
    """Get current key information for logging"""
    if not GEMINI_API_KEYS:
        return "No keys available"
    return f"Key {_current_key_index + 1}/{len(GEMINI_API_KEYS)}"

def get_tool_server_token():
    """Get or refresh tool server authentication token"""
    global _tool_server_token, _token_expiry
    
    # Check if we have a valid token
    if _tool_server_token and _token_expiry:
        from datetime import datetime, timedelta
        if datetime.utcnow() < _token_expiry - timedelta(minutes=5):
            return _tool_server_token
    
    # Get new token
    try:
        response = requests.post(
            f"{TOOL_SERVER_URL}/auth/login",
            json={
                'username': TOOL_SERVER_USERNAME,
                'password': TOOL_SERVER_PASSWORD
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            _tool_server_token = data['token']
            
            # Set expiry (subtract 5 minutes for safety)
            from datetime import datetime, timedelta
            expires_in = data.get('expires_in', 86400)  # Default 24 hours
            _token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            
            logger.info("✓ Tool server token obtained")
            return _tool_server_token
        else:
            logger.error(f"Failed to authenticate with tool server: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error getting tool server token: {str(e)}")
        return None

def search_tools(query, max_results=3, category=None):
    """Search for tools on tool server"""
    try:
        response = requests.post(
            f"{TOOL_SERVER_URL}/tools/search",
            json={
                'query': query,
                'max_results': max_results,
                'category': category
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('results', [])
        else:
            logger.error(f"Tool search failed: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error searching tools: {str(e)}")
        return []

def get_tool_context_for_llm(query, max_tools=3):
    """Get formatted tool context for LLM - excluding bugged tools"""
    try:
        response = requests.post(
            f"{TOOL_SERVER_URL}/tools/context/search",
            json={
                'query': query,
                'max_tools': max_tools,
                'exclude_bugged': True  # NEW: Exclude bugged tools
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            context = data.get('context', '')
            
            # Ensure context is not empty and well-formatted
            if not context or context.strip() == "":
                logger.warning(f"Empty tool context received for query: {query}")
                return "No tools found matching the query."
            
            return context
        else:
            logger.error(f"Failed to get tool context: {response.status_code} - {response.text}")
            return ''
    except requests.exceptions.Timeout:
        logger.error(f"Timeout getting tool context for query: {query}")
        return ''
    except Exception as e:
        logger.error(f"Error getting tool context: {str(e)}")
        return ''

def execute_tool(tool_name, params):
    """Execute a tool on tool server"""
    try:
        token = get_tool_server_token()
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        response = requests.post(
            f"{TOOL_SERVER_URL}/tools/{tool_name}/execute",
            json=params,
            headers=headers
        )
        
        return response.json()
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return {
            'success': False,
            'error': f'Failed to execute tool: {str(e)}'
        }

def save_tool_to_file(tool_code, tool_name):
    """Save generated tool code to tools directory"""
    try:
        tools_dir = Path('./tools')
        tools_dir.mkdir(exist_ok=True)
        
        # Sanitize filename
        safe_name = re.sub(r'[^\w\-]', '_', tool_name.lower())
        filepath = tools_dir / f"{safe_name}.py"
        
        with open(filepath, 'w') as f:
            f.write(tool_code)
        
        logger.info(f"✓ Saved tool to {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Error saving tool: {str(e)}")
        return None

def reload_tools_on_server():
    """Trigger tool server to reload tools"""
    try:
        token = get_tool_server_token()
        if not token:
            return False
        
        response = requests.post(
            f"{TOOL_SERVER_URL}/tools/reload",
            headers={'Authorization': f'Bearer {token}'}
        )
        
        if response.status_code == 200:
            logger.info("✓ Tool server reloaded")
            return True
        else:
            logger.error(f"Failed to reload tools: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error reloading tools: {str(e)}")
        return False
def build_system_prompt():
    """Build comprehensive system prompt for Gemini"""
    return """You are an AI assistant with access to a dynamic tool system. Your role is to help users by:

1. **Understanding user queries** and determining if tools are needed
2. **Using available tools** when they can help answer the query
3. **Creating new tools** when needed tools don't exist
4. **NEVER give up** - if you can't answer directly, CREATE A TOOL to help

## Available Actions:

### 1. Using Existing Tools
**CRITICAL: If a tool exists that can solve the query, USE IT. Do not search for alternatives.**
**IMPORTANT: Available tools are pre-filtered to exclude bugged tools. All shown tools are working.**

When tools are provided in the context, analyze them carefully and use them if appropriate:
```json
{
    "action": "use_tool",
    "tool_name": "exact_tool_name_from_context",
    "parameters": {
        "param1": "value1"
    },
    "reasoning": "Why you're using this tool"
}
```

### 2. Searching for More Tools
```json
{
    "action": "search_tools",
    "query": "specific capability needed",
    "reasoning": "Why current tools don't match and what I'm looking for"
}
```

### 3. Creating New Tools
```json
{
    "action": "create_tool",
    "tool_name": "descriptive_tool_name",
    "tool_code": "complete Python code here",
    "reasoning": "Why this tool is needed"
}
```

### 4. Final Response
**CRITICAL FORMAT: When providing the final answer, use this EXACT structure:**
```json
{
    "action": "respond",
    "response": "Your complete answer to the user's query here. Include all relevant information from tool results.",
    "reasoning": "Optional: Brief explanation of how you arrived at this answer"
}
```

**IMPORTANT:**
- The "response" field MUST contain your complete answer
- Do NOT use "answer" field - use "response"
- Include all relevant information in the response
- Make the response conversational and complete

## CRITICAL TOOL CREATION RULES:

### ✅ REQUIRED Error Handling Pattern:
**ALL tools MUST raise exceptions on failure - NEVER return empty results silently!**

```python
from tool_server import tool
import requests

@tool(name="example_tool", category="example", tags=["demo"], requirements=["requests"])
def example_tool(param: str) -> dict:
    \"\"\"Tool description.
    
    Args:
        param: Parameter description
    
    Returns:
        Result dictionary with actual data
    
    Raises:
        RuntimeError: If tool execution fails
        ValueError: If parameters are invalid
    \"\"\"
    try:
        # Your tool logic here
        result = some_operation(param)
        
        # CRITICAL: Validate result before returning
        if not result or len(result) == 0:
            raise RuntimeError(f"Tool failed to get data for: {param}")
        
        return result
        
    except requests.RequestException as e:
        # Re-raise network errors with context
        raise RuntimeError(f"Network request failed: {str(e)}")
    except Exception as e:
        # Re-raise all other errors with context
        raise RuntimeError(f"Tool execution failed: {str(e)}")
```

### ❌ WRONG - Don't Do This:
```python
# BAD: Silent failure with empty results
def bad_tool(query: str) -> dict:
    try:
        results = fetch_data(query)
        return {"results": results, "count": len(results)}  # Returns empty on failure!
    except:
        return {"results": [], "count": 0}  # Silent failure - BAD!
```

### ✅ CORRECT - Do This:
```python
# GOOD: Raises exception on failure
def good_tool(query: str) -> dict:
    try:
        results = fetch_data(query)
        
        # Validate results
        if not results:
            raise RuntimeError(f"No data found for query: {query}")
        
        return {"results": results, "count": len(results)}
        
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch data: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Tool execution failed: {str(e)}")
```

### Required Tool Structure:
```python
from tool_server import tool
import requests  # or other required libraries

@tool(
    name="tool_name",  # Unique, descriptive name
    category="category",  # web, api, data, computation, etc.
    tags=["tag1", "tag2"],  # Searchable tags
    requirements=["requests", "beautifulsoup4"]  # pip packages needed
)
def tool_function(param1: str, param2: int = 10) -> dict:
    \"\"\"Clear description of what the tool does.
    
    Args:
        param1: Description of required parameter
        param2: Description of optional parameter (default: 10)
    
    Returns:
        Dictionary with results. Example: {"data": [...], "count": 5}
    
    Raises:
        RuntimeError: If execution fails
        ValueError: If parameters are invalid
    \"\"\"
    # ALWAYS validate inputs
    if not param1 or not param1.strip():
        raise ValueError("param1 cannot be empty")
    
    try:
        # Tool logic here
        result = perform_operation(param1, param2)
        
        # ALWAYS validate output before returning
        if not result:
            raise RuntimeError("Operation returned no results")
        
        return {"data": result, "count": len(result)}
        
    except SpecificError as e:
        # Catch specific errors and re-raise with context
        raise RuntimeError(f"Specific operation failed: {str(e)}")
    except Exception as e:
        # Catch all other errors
        raise RuntimeError(f"Tool execution failed: {str(e)}")
```

### Common Tool Patterns:

**Web Search Tool (with proper error handling):**
```python
from tool_server import tool
import requests
from bs4 import BeautifulSoup

@tool(name="web_search", category="web", tags=["search", "internet"], requirements=["requests", "beautifulsoup4"])
def web_search(query: str, num_results: int = 5) -> dict:
    \"\"\"Search the web for information using DuckDuckGo.
    
    Args:
        query: Search query string
        num_results: Number of results to return (default: 5)
    
    Returns:
        Dictionary with search results: {"results": [...], "count": int}
    
    Raises:
        ValueError: If query is empty
        RuntimeError: If search fails or returns no results
    \"\"\"
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
```

**API Tool (with proper error handling):**
```python
from tool_server import tool
import requests

@tool(name="fetch_api_data", category="api", tags=["api", "http"], requirements=["requests"])
def fetch_api_data(url: str, params: dict = None) -> dict:
    \"\"\"Fetch data from an API endpoint.
    
    Args:
        url: API endpoint URL
        params: Optional query parameters dictionary
    
    Returns:
        API response data as dictionary
    
    Raises:
        ValueError: If URL is invalid
        RuntimeError: If API request fails
    \"\"\"
    # Validate input
    if not url or not url.startswith(('http://', 'https://')):
        raise ValueError(f"Invalid URL: {url}")
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Validate response
        if not data:
            raise RuntimeError(f"API returned empty response from: {url}")
        
        return data
        
    except requests.Timeout:
        raise RuntimeError(f"API request timed out: {url}")
    except requests.HTTPError as e:
        raise RuntimeError(f"API returned error {e.response.status_code}: {str(e)}")
    except requests.RequestException as e:
        raise RuntimeError(f"Network error calling API: {str(e)}")
    except ValueError as e:
        raise RuntimeError(f"API response is not valid JSON: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"API request failed: {str(e)}")
```

**Weather Tool Example:**
```python
from tool_server import tool
import requests

@tool(name="get_weather", category="api", tags=["weather", "forecast"], requirements=["requests"])
def get_weather(location: str) -> dict:
    \"\"\"Get current weather for a location using wttr.in service.
    
    Args:
        location: City name or location query
    
    Returns:
        Weather information dictionary
    
    Raises:
        ValueError: If location is empty
        RuntimeError: If weather fetch fails
    \"\"\"
    if not location or not location.strip():
        raise ValueError("Location cannot be empty")
    
    try:
        url = f"https://wttr.in/{location}?format=j1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data or 'current_condition' not in data:
            raise RuntimeError(f"Invalid weather data for location: {location}")
        
        current = data['current_condition'][0]
        
        return {
            'location': location,
            'temperature': current.get('temp_C', 'N/A'),
            'condition': current.get('weatherDesc', [{}])[0].get('value', 'N/A'),
            'humidity': current.get('humidity', 'N/A'),
            'wind_speed': current.get('windspeedKmph', 'N/A')
        }
        
    except requests.Timeout:
        raise RuntimeError(f"Weather request timed out for: {location}")
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch weather: {str(e)}")
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Failed to parse weather data: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Weather lookup failed: {str(e)}")
```

## Critical Rules:
- **NEVER say "I cannot" without trying to create a tool first**
- **ALWAYS raise exceptions on tool failures** - never return empty results silently
- **ALWAYS validate inputs and outputs** in tools
- **If a tool is marked as BUGGED, create a NEW tool with a DIFFERENT name**
- **DO NOT retry bugged tools** - the system already tried twice
- If you need web access, create a web search/scraping tool
- If you need APIs, create an API calling tool
- If you need computation, create a calculation tool
- ALWAYS respond with valid JSON
- Use \\n for newlines in tool_code strings
- Match tool names exactly as provided in context
- After creating a tool, USE IT in the next iteration
- Include necessary imports (requests, BeautifulSoup, etc.) in tool code

**Remember: Your goal is to SOLVE the user's query, not to explain why you can't!**
**Remember: Tools must FAIL LOUDLY with exceptions, not silently with empty results!**
**Remember: Bugged tools are automatically excluded from available tools - create new ones with different names!**
**Remember: Always use "response" field for final answers, never "answer"!**"""

def parse_gemini_response(response_text):
    """Parse Gemini's JSON response, handling multiline code blocks"""
    try:
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        
        # Clean up the response
        response_text = response_text.strip()
        
        # Handle escaped newlines in tool_code by converting them to actual newlines
        # This fixes the "Invalid control character" error
        try:
            # First attempt: direct parse
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            # Second attempt: replace literal \n with actual newlines
            # Find tool_code field and process it
            code_pattern = r'"tool_code"\s*:\s*"([^"]*(?:\\.[^"]*)*)"'
            
            def fix_code_field(match):
                code_content = match.group(1)
                # Unescape the content properly
                code_content = code_content.encode().decode('unicode_escape')
                # Re-escape for JSON but keep newlines as \n
                code_content = json.dumps(code_content)[1:-1]  # Remove outer quotes
                return f'"tool_code": "{code_content}"'
            
            fixed_text = re.sub(code_pattern, fix_code_field, response_text, flags=re.DOTALL)
            parsed = json.loads(fixed_text)
        
        return parsed
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        logger.error(f"Response text preview: {response_text[:500]}")
        
        # Try to extract action and basic info even if full parse fails
        action_match = re.search(r'"action"\s*:\s*"(\w+)"', response_text)
        if action_match:
            action = action_match.group(1)
            
            if action == "create_tool":
                # Try to extract tool_code and tool_name
                name_match = re.search(r'"tool_name"\s*:\s*"([^"]+)"', response_text)
                code_match = re.search(r'"tool_code"\s*:\s*"([^"]+(?:\n|\\n)[^"]*)"', response_text, re.DOTALL)
                
                if name_match and code_match:
                    tool_name = name_match.group(1)
                    tool_code = code_match.group(1)
                    # Decode escaped sequences
                    tool_code = tool_code.encode().decode('unicode_escape')
                    
                    return {
                        'action': 'create_tool',
                        'tool_name': tool_name,
                        'tool_code': tool_code,
                        'reasoning': 'Extracted from malformed JSON'
                    }
            
            # For other actions, try basic extraction
            response_match = re.search(r'"response"\s*:\s*"([^"]+)"', response_text)
            if response_match:
                return {
                    'action': action,
                    'response': response_match.group(1)
                }
        
        # Final fallback: treat as direct response
        return {
            'action': 'respond',
            'response': response_text
        }

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    # Check tool server connection
    try:
        response = requests.get(f"{TOOL_SERVER_URL}/health")
        tool_server_ok = response.status_code == 200
    except:
        tool_server_ok = False
    
    # Check Gemini configuration
    gemini_ok = GEMINI_API_KEY is not None
    
    return jsonify({
        'status': 'healthy' if (tool_server_ok and gemini_ok) else 'degraded',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {
            'tool_server': 'connected' if tool_server_ok else 'disconnected',
            'gemini': 'configured' if gemini_ok else 'not configured'
        }
    })

@app.route('/query', methods=['POST'])
def process_query():
    """Main endpoint to process user queries with Gemini and tools"""
    try:
        data = request.get_json()
        
        if not data or not data.get('query'):
            return jsonify({'error': 'Missing query parameter'}), 400
        
        query = data.get('query')
        max_tools = min(int(data.get('max_tools', 3)), 5)
        conversation_history = data.get('history', [])
        use_docker = data.get('use_docker', True)
        max_iterations = int(data.get('max_iterations', 10))  # Prevent infinite loops
        
        logger.info(f"Processing query: {query}")
        
        # Temporarily disable auto-reload during query processing
        # This prevents Flask from restarting when tools are created
        original_use_reloader = app.debug
        if original_use_reloader:
            logger.info("⚠️  Temporarily disabling auto-reload during query processing")
        
        # Initialize conversation history for this query
        internal_history = []
        actions_taken = []
        
        # Start the agent loop
        result = agent_loop(
            query=query,
            max_tools=max_tools,
            use_docker=use_docker,
            max_iterations=max_iterations,
            internal_history=internal_history,
            actions_taken=actions_taken
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Failed to process query',
            'details': str(e)
        }), 500

def agent_loop(query, max_tools, use_docker, max_iterations, internal_history, actions_taken):
    """
    Main agent loop that continues until Gemini provides a final response
    """
    import time
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Agent iteration {iteration}/{max_iterations}")
        
        # Build context based on conversation history
        if iteration == 1:
            # First iteration: get initial tool context
            tool_context = get_tool_context_for_llm(query, max_tools=max_tools)
            
            if not tool_context:
                logger.warning("No tool context available")
                tool_context = "No relevant tools found. You may need to search for tools, create a new tool, or provide a direct response."
            
            prompt = build_initial_prompt(query, tool_context, internal_history)
        else:
            # Subsequent iterations: use conversation history
            prompt = build_continuation_prompt(query, internal_history)
        
        # Send to Gemini with enhanced retry logic and key rotation
        logger.info(f"Sending prompt to Gemini (iteration {iteration}, {get_current_key_info()})...")
        
        # Try each API key twice before giving up
        max_retries = len(GEMINI_API_KEYS) * 2 if GEMINI_API_KEYS else 6
        base_retry_delay = 5  # Increased from 2 to 5 seconds
        
        response = None
        for retry in range(max_retries):
            try:
                # Add delay before each request (except first)
                if retry > 0:
                    # Exponential backoff: 5s, 10s, 20s, 40s, etc.
                    delay = min(base_retry_delay * (2 ** (retry - 1)), 60)  # Cap at 60 seconds
                    logger.info(f"⏳ Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                
                response = send_message_to_gemini_model(
                    model=GEMINI_MODEL,
                    message=prompt,
                    stream=False,
                    system_message=""
                )
                
                # Success - add a small delay after successful request
                logger.info("✓ Request successful, adding 3 second cooldown...")
                time.sleep(3)
                break  # Success, exit retry loop
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a rate limit or overload error
                if any(keyword in error_msg for keyword in ['overloaded', 'rate limit', 'quota', '429', '503', 'resource_exhausted']):
                    if retry < max_retries - 1:
                        # Rotate to next API key
                        old_key_info = get_current_key_info()
                        get_next_gemini_key()
                        new_key_info = get_current_key_info()
                        
                        logger.warning(f"⚠️  Model overloaded/rate limited on {old_key_info}")
                        logger.info(f"🔄 Rotating to {new_key_info} (attempt {retry + 1}/{max_retries})")
                        
                        continue
                    else:
                        logger.error(f"❌ Model overloaded after {max_retries} attempts across all API keys")
                        return {
                            'success': False,
                            'error': f'All Gemini API keys are currently overloaded after {max_retries} attempts. The service is experiencing high load. Please try again in a few minutes.',
                            'error_type': 'all_keys_overloaded',
                            'iterations': iteration,
                            'actions_taken': actions_taken,
                            'keys_tried': len(GEMINI_API_KEYS) if GEMINI_API_KEYS else 0,
                            'total_attempts': max_retries
                        }
                else:
                    # Different error type - log and return
                    logger.error(f"❌ Gemini API error ({get_current_key_info()}): {str(e)}")
                    
                    # If it's a transient error, retry with exponential backoff
                    if retry < max_retries - 1 and any(keyword in error_msg for keyword in ['timeout', 'connection', 'network']):
                        logger.warning(f"⚠️  Transient error, will retry...")
                        continue
                    
                    return {
                        'success': False,
                        'error': f'Gemini API error: {str(e)}',
                        'error_type': 'api_error',
                        'iterations': iteration,
                        'actions_taken': actions_taken,
                        'current_key': get_current_key_info()
                    }
        
        # Check if we got a response
        if response is None:
            logger.error("❌ Failed to get response from Gemini after all retries")
            return {
                'success': False,
                'error': 'Failed to get response from Gemini after all retry attempts',
                'error_type': 'no_response',
                'iterations': iteration,
                'actions_taken': actions_taken
            }
        
        logger.info(f"Gemini response preview: {response[:200]}...")
        
        # Parse response
        parsed_response = parse_gemini_response(response)
        action = parsed_response.get('action')
        
        logger.info(f"Iteration {iteration}: Action = {action}")
        
        # Record this interaction
        actions_taken.append({
            'iteration': iteration,
            'action': action,
            'details': parsed_response
        })
        
        # Handle different actions
        if action == 'respond':
            # Final response - exit loop
            logger.info("Gemini provided final response, exiting agent loop")
            
            # Extract response from multiple possible fields
            response_text = (
                parsed_response.get('response') or 
                parsed_response.get('answer') or 
                parsed_response.get('details', {}).get('answer') or
                parsed_response.get('details', {}).get('response') or
                ''
            )
            
            if not response_text:
                logger.warning(f"Empty response detected. Full parsed response: {parsed_response}")
                response_text = "I was unable to generate a proper response. Please try rephrasing your question."
            
            return {
                'success': True,
                'action': 'respond',
                'response': response_text,
                'reasoning': parsed_response.get('reasoning', ''),
                'iterations': iteration,
                'actions_taken': actions_taken,
                'conversation_history': internal_history
            }
        
        elif action == 'use_tool':
            # Execute tool and continue loop
            tool_result = handle_use_tool(
                parsed_response, 
                query, 
                use_docker, 
                internal_history
            )
            
            if not tool_result['success']:
                # Tool execution failed, let Gemini know
                internal_history.append({
                    'role': 'system',
                    'content': f"Tool execution failed: {tool_result.get('error', 'Unknown error')}"
                })
            
            # Add delay between iterations (reduced since we now wait after tool execution)
            logger.info("⏳ Waiting 1 second before next iteration...")
            time.sleep(1)
            continue
        
        elif action == 'search_tools':
            # Search for tools and continue loop
            search_result = handle_search_tools(
                parsed_response,
                query,
                max_tools,
                internal_history
            )
            
            # Add delay between iterations
            logger.info("⏳ Waiting 2 seconds before next iteration...")
            time.sleep(2)
            continue
        
        elif action == 'create_tool':
            # Create tool and continue loop
            create_result = handle_create_tool(
                parsed_response,
                internal_history
            )
            
            # No additional delay here - handle_create_tool already waits 5 seconds
            logger.info("⏳ Proceeding to next iteration...")
            continue
        
        else:
            # Unknown action, add to history and let Gemini try again
            logger.warning(f"Unknown action: {action}")
            internal_history.append({
                'role': 'system',
                'content': f"Unknown action '{action}' received. Please choose from: use_tool, search_tools, create_tool, or respond."
            })
            
            # Add delay between iterations
            logger.info("⏳ Waiting 2 seconds before next iteration...")
            time.sleep(2)
            continue
    
    # Max iterations reached
    logger.warning(f"Max iterations ({max_iterations}) reached")
    return {
        'success': False,
        'error': 'Max iterations reached without final response',
        'iterations': iteration,
        'actions_taken': actions_taken,
        'conversation_history': internal_history,
        'last_action': actions_taken[-1] if actions_taken else None
    }

def build_initial_prompt(query, tool_context, internal_history):
    """Build the initial prompt for the first iteration"""
    system_prompt = build_system_prompt()
    
    conversation_context = ""
    if internal_history:
        conversation_context = "\n## Conversation History:\n"
        for msg in internal_history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            conversation_context += f"{role.capitalize()}: {content}\n"
        conversation_context += "\n"
    
    return f"""{system_prompt}

## Available Tools:
{tool_context}
{conversation_context}
## User Query:
{query}

Analyze the available tools carefully. Choose the appropriate action and respond with valid JSON."""

def build_continuation_prompt(query, internal_history):
    """Build prompt for continuation iterations based on history"""
    system_prompt = build_system_prompt()
    
    conversation_context = "\n## Conversation History:\n"
    for msg in internal_history:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        conversation_context += f"{role.capitalize()}: {content}\n"
    conversation_context += "\n"
    
    return f"""{system_prompt}
{conversation_context}
## User's Original Query:
{query}

Based on the conversation history above, decide your next action. If you have enough information to answer the user's query, use the 'respond' action with a clear, natural language answer.

Respond with valid JSON."""


def handle_use_tool(parsed_response, query, use_docker, internal_history):
    """Handle use_tool action with retry logic"""
    import time
    
    tool_name = parsed_response.get('tool_name')
    parameters = parsed_response.get('parameters', {})
    reasoning = parsed_response.get('reasoning', '')
    
    logger.info(f"Executing tool: {tool_name} with params: {parameters}")
    
    # Add decision to history
    internal_history.append({
        'role': 'assistant',
        'content': f"I will use the tool '{tool_name}' with parameters {json.dumps(parameters)}. Reasoning: {reasoning}"
    })
    
    # Retry logic: Try up to 2 times
    max_retries = 2
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"Tool execution attempt {attempt}/{max_retries} for '{tool_name}'")
        
        # Execute tool
        execution_result = execute_tool_with_docker(tool_name, parameters, use_docker)
        
        # Wait 2 seconds after getting response from tool server
        logger.info("⏳ Waiting 2 seconds after tool execution response...")
        time.sleep(2)
        
        # Check if execution was successful
        if execution_result.get('success'):
            result_content = f"""Tool '{tool_name}' executed successfully (attempt {attempt}/{max_retries}).
Execution Method: {'Docker Container' if execution_result.get('executed_in_docker') else 'Direct'}
Result: {json.dumps(execution_result.get('result'), indent=2)}

Now use this result to answer the user's query. Do NOT create the tool again."""
            
            internal_history.append({
                'role': 'system',
                'content': result_content
            })
            
            return execution_result
        else:
            # Execution failed
            error_msg = execution_result.get('error', 'Unknown error')
            last_error = error_msg
            
            # Check if tool is marked as bugged
            if execution_result.get('is_bugged'):
                # Tool is already marked as bugged, don't retry
                result_content = f"""Tool '{tool_name}' is marked as BUGGED and cannot be used.
Error: {error_msg}
Failure Count: {execution_result.get('failure_count', 'unknown')}

This tool has failed multiple times and has been flagged as problematic.

DO NOT:
- Try to use this tool again
- Create a new version of this tool with the same name

INSTEAD:
- Create a NEW tool with a DIFFERENT name that solves the same problem
- Use a different approach or different tool
- If no alternative exists, explain to the user that this functionality is currently unavailable"""
                
                internal_history.append({
                    'role': 'system',
                    'content': result_content
                })
                
                return execution_result
            
            # Not yet marked as bugged, but failed
            if attempt < max_retries:
                # Retry with longer delay
                retry_delay = 3  # Increased from 1 to 3 seconds
                retry_content = f"""Tool '{tool_name}' execution failed (attempt {attempt}/{max_retries}).
Error: {error_msg}

Waiting {retry_delay} seconds before retrying..."""
                
                internal_history.append({
                    'role': 'system',
                    'content': retry_content
                })
                
                logger.info(f"⏳ Waiting {retry_delay} seconds before tool retry...")
                time.sleep(retry_delay)
                continue
            else:
                # Max retries reached - tool will be marked as bugged
                result_content = f"""Tool '{tool_name}' execution FAILED after {max_retries} attempts.
Last Error: {error_msg}

The tool has been automatically marked as BUGGED due to repeated failures.

Possible reasons:
1. The tool has a bug in its implementation
2. Required dependencies are missing
3. Network/API issues
4. Invalid parameters

DO NOT:
- Try to use this tool again
- Create the tool again with the same name

INSTEAD:
- Create a CORRECTED tool with a DIFFERENT name
- Use a completely different approach
- Explain the issue to the user if no workaround exists

Error details: {json.dumps(execution_result, indent=2)}"""
                
                internal_history.append({
                    'role': 'system',
                    'content': result_content
                })
                
                return execution_result
    
    # Should not reach here, but handle it anyway
    return {
        'success': False,
        'error': last_error or 'Tool execution failed after all retries'
    }

def handle_search_tools(parsed_response, query, max_tools, internal_history):
    """Handle search_tools action"""
    search_query = parsed_response.get('query', '')
    reasoning = parsed_response.get('reasoning', '')
    
    logger.info(f"Searching for tools: {search_query}")
    
    # Add decision to history
    internal_history.append({
        'role': 'assistant',
        'content': f"I will search for tools with query '{search_query}'. Reasoning: {reasoning}"
    })
    
    # Search for tools
    search_results = search_tools(search_query, max_results=max_tools)
    
    # Format search results
    if search_results:
        results_content = f"Found {len(search_results)} tools:\n\n"
        for i, tool in enumerate(search_results, 1):
            results_content += f"""{i}. Tool: {tool['tool_name']}
   - Category: {tool['category']}
   - Description: {tool['description']}
   - Required Parameters: {', '.join(tool['required_params'])}
   - Optional Parameters: {', '.join(tool.get('optional_params', {}).keys())}
   - Tags: {', '.join(tool['tags'])}
   - Relevance Score: {tool['relevance_score']:.2f}

"""
    else:
        results_content = f"No tools found matching query '{search_query}'"
    
    # Add results to history
    internal_history.append({
        'role': 'system',
        'content': results_content
    })
    
    return {
        'success': True,
        'results': search_results
    }

def handle_create_tool(parsed_response, internal_history):
    """Handle create_tool action"""
    import time
    
    tool_code = parsed_response.get('tool_code', '')
    tool_name = parsed_response.get('tool_name', '')
    reasoning = parsed_response.get('reasoning', '')
    
    logger.info(f"Creating new tool: {tool_name}")
    
    # Add decision to history
    internal_history.append({
        'role': 'assistant',
        'content': f"I will create a new tool '{tool_name}'. Reasoning: {reasoning}"
    })
    
    # Save tool to file
    filepath = save_tool_to_file(tool_code, tool_name)
    
    if filepath:
        # Reload tools on server
        reload_success = reload_tools_on_server()
        
        # If reload failed, notify but don't fail completely
        # Flask's auto-reloader will pick it up if in development mode
        reload_message = "Tool server reloaded successfully" if reload_success else "Tool server reload failed (will reload automatically in dev mode)"
        
        # Wait 5 seconds after tool creation and reload to ensure tool is ready
        if reload_success:
            logger.info("⏳ Waiting 5 seconds for tool server to fully reload...")
            time.sleep(5)
        else:
            # Wait for auto-reloader if in dev mode
            if os.getenv('FLASK_ENV') == 'development':
                logger.info("⏳ Waiting 5 seconds for Flask auto-reloader...")
                time.sleep(5)
        
        result_content = f"""Tool '{tool_name}' created successfully.
File saved to: {filepath}
{reload_message}

IMPORTANT: You MUST use this tool in the next action. Do NOT create it again.
Use the 'use_tool' action with the tool name '{tool_name}'."""
        
        internal_history.append({
            'role': 'system',
            'content': result_content
        })
        
        return {
            'success': True,
            'filepath': filepath,
            'reloaded': reload_success
        }
    else:
        error_content = f"Failed to create tool '{tool_name}'"
        
        internal_history.append({
            'role': 'system',
            'content': error_content
        })
        
        return {
            'success': False,
            'error': 'Failed to save tool file'
        }

def execute_tool_with_docker(tool_name, params, use_docker=True):
    """Execute a tool on tool server with optional Docker execution"""
    try:
        token = get_tool_server_token()
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        # Add use_docker query parameter
        url = f"{TOOL_SERVER_URL}/tools/{tool_name}/execute"
        if use_docker:
            url += "?use_docker=true"
        else:
            url += "?use_docker=false"
        
        response = requests.post(
            url,
            json=params,
            headers=headers,
            timeout=60  # Increase timeout for Docker execution
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Tool execution failed: {response.status_code} - {response.text}")
            return {
                'success': False,
                'error': f'Tool execution failed: {response.text}',
                'executed_in_docker': False
            }
    except requests.exceptions.Timeout:
        logger.error(f"Timeout executing tool {tool_name}")
        return {
            'success': False,
            'error': 'Tool execution timeout',
            'executed_in_docker': False
        }
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return {
            'success': False,
            'error': f'Failed to execute tool: {str(e)}',
            'executed_in_docker': False
        }

@app.route('/tools/search', methods=['POST'])
def search_tools_endpoint():
    """Proxy endpoint for tool search"""
    data = request.get_json()
    
    if not data or not data.get('query'):
        return jsonify({'error': 'Missing query parameter'}), 400
    
    query = data.get('query')
    max_results = min(int(data.get('max_results', 3)), 5)
    category = data.get('category')
    
    results = search_tools(query, max_results=max_results, category=category)
    
    return jsonify({
        'query': query,
        'results': results
    })

@app.route('/tools/execute', methods=['POST'])
def execute_tool_endpoint():
    """Proxy endpoint for tool execution"""
    data = request.get_json()
    
    if not data or not data.get('tool_name'):
        return jsonify({'error': 'Missing tool_name parameter'}), 400
    
    tool_name = data.get('tool_name')
    parameters = data.get('parameters', {})
    
    result = execute_tool(tool_name, parameters)
    
    return jsonify(result)

@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify({
        'tool_server': {
            'url': TOOL_SERVER_URL,
            'authenticated': _tool_server_token is not None
        },
        'gemini': {
            'model': GEMINI_MODEL,
            'configured': len(GEMINI_API_KEYS) > 0,
            'api_keys_count': len(GEMINI_API_KEYS),
            'current_key': get_current_key_info() if GEMINI_API_KEYS else 'N/A'
        }
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.getenv('TOOL_USER_PORT', 5002))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Tool User Server on port {port}")
    logger.info(f"Tool Server URL: {TOOL_SERVER_URL}")
    logger.info(f"Gemini Model: {GEMINI_MODEL}")
    logger.info(f"Gemini API Keys: {len(GEMINI_API_KEYS)} loaded")
    logger.info(f"Debug mode: {debug}")
    
    # Configure reloader to exclude tools directory
    if debug:
        logger.warning("⚠️  Running in debug mode - tool creation may trigger restarts")
        logger.info("💡 Set FLASK_ENV=production to disable auto-reload")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=False  # Disable auto-reload to prevent interruptions
    )