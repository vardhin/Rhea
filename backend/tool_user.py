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
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')

# Initialize Gemini
if GEMINI_API_KEY:
    set_api_key(GEMINI_API_KEY)
    logger.info("✓ Gemini API key configured")
else:
    logger.warning("⚠ Gemini API key not found in environment")

# Tool Server Authentication Token Cache
_tool_server_token = None
_token_expiry = None

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
    """Get formatted tool context for LLM"""
    try:
        response = requests.post(
            f"{TOOL_SERVER_URL}/tools/context/search",
            json={
                'query': query,
                'max_tools': max_tools
            },
            timeout=10  # Add timeout
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

**Tool Usage Priority:**
- If ANY available tool can handle the request → use_tool
- Mathematical calculations → use calculator/math tools (multiply, add, calculate)
- Text processing → use text manipulation tools
- File operations → use file tools
- Data analysis → use data processing tools
- Web searches → use web search/scraping tools
- API calls → use HTTP/API tools

### 2. Searching for More Tools
**Search if:**
- No available tool matches but one MIGHT exist
- You need to check what tools are available before creating
```json
{
    "action": "search_tools",
    "query": "specific capability needed",
    "reasoning": "Why current tools don't match and what I'm looking for"
}
```

### 3. Creating New Tools
**YOU SHOULD CREATE A TOOL IF:**
- The query requires external data (web search, API calls, file reading)
- The query needs computation that current tools can't handle
- The query needs any capability not currently available
- You searched and found no suitable tool

**DO NOT refuse to answer - CREATE A TOOL INSTEAD!**

Examples of when to create tools:
- "What's the weather?" → Create a weather API tool
- "Search for X news" → Create a web search/scraping tool
- "Get latest Y" → Create a data fetching tool
- "Calculate complex formula" → Create a specialized calculator
- "Process this data" → Create a data processing tool

**Tool Creation Template:**
```json
{
    "action": "create_tool",
    "tool_code": "from tool_server import tool\nimport requests\n\n@tool(name=\"tool_name\", category=\"category\", tags=[\"tag1\", \"tag2\"], requirements=[\"library1\",\"libarary2\"])\ndef function_name(param1: str) -> dict:\n    \"\"\"Tool description.\n    \n    Args:\n        param1: Parameter description\n    \n    Returns:\n        Result dictionary\n    \"\"\"\n    # Implementation\n    result = {}  # Your logic here\n    return result",
    "tool_name": "tool_name",
    "reasoning": "Why this tool is needed and what it will do"
}
```

**Common Tool Patterns:**

**Web Search Tool:**
```python
from tool_server import tool
import requests
from bs4 import BeautifulSoup

@tool(name="web_search", category="web", tags=["search", "internet"], requirements=["requests","bs4"])
def web_search(query: str, num_results: int = 5) -> dict:
    \"\"\"Search the web for information.
    
    Args:
        query: Search query
        num_results: Number of results to return
    
    Returns:
        Search results with titles and snippets
    \"\"\"
    # Use a search API or web scraping
    # For demo, using DuckDuckGo HTML scraping
    url = f"https://html.duckduckgo.com/html/?q={query}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    results = []
    for result in soup.find_all('div', class_='result')[:num_results]:
        title = result.find('a', class_='result__a')
        snippet = result.find('a', class_='result__snippet')
        if title and snippet:
            results.append({
                'title': title.get_text(),
                'snippet': snippet.get_text(),
                'url': title.get('href')
            })
    
    return {'results': results, 'count': len(results)}
```

**API Tool:**
```python
from tool_server import tool
import requests

@tool(name="fetch_api_data", category="api", tags=["api", "data"], requirements=["requests"])
def fetch_api_data(url: str, params: dict = None) -> dict:
    \"\"\"Fetch data from an API.
    
    Args:
        url: API endpoint URL
        params: Query parameters
    
    Returns:
        API response data
    \"\"\"
    response = requests.get(url, params=params)
    return response.json()
```

### 4. Direct Response
**ONLY use this when:**
- Question is purely informational (definitions, explanations)
- No external data or computation needed
- You have the answer in your training data

```json
{
    "action": "respond",
    "response": "Your answer"
}
```

## Decision Priority:
1. **First**: Check if an available tool matches → use_tool
2. **Second**: If query needs external data/computation → search_tools
3. **Third**: If no tool found and capability needed → **CREATE_TOOL** (DO NOT REFUSE!)
4. **Last**: Only for pure informational queries → respond

## Critical Rules:
- **NEVER say "I cannot" without trying to create a tool first**
- If you need web access, create a web search/scraping tool
- If you need APIs, create an API calling tool
- If you need computation, create a calculation tool
- ALWAYS respond with valid JSON
- Use \\n for newlines in tool_code strings
- Match tool names exactly as provided in context
- After creating a tool, USE IT in the next iteration
- Include necessary imports (requests, BeautifulSoup, etc.) in tool code

## Multi-Step Workflow Example:
User: "What's the latest news about X?"
Step 1: search_tools → No web search tool found
Step 2: create_tool → Create web_search tool
Step 3: use_tool → Use newly created web_search tool
Step 4: respond → Provide answer based on tool result

**Remember: Your goal is to SOLVE the user's query, not to explain why you can't!**"""

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
        
        # Send to Gemini
        logger.info(f"Sending prompt to Gemini (iteration {iteration})...")
        response = send_message_to_gemini_model(
            model=GEMINI_MODEL,
            message=prompt,
            stream=False,
            system_message=""
        )
        
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
            return {
                'success': True,
                'action': 'respond',
                'response': parsed_response.get('response', ''),
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
            
            # Continue to next iteration
            continue
        
        elif action == 'search_tools':
            # Search for tools and continue loop
            search_result = handle_search_tools(
                parsed_response,
                query,
                max_tools,
                internal_history
            )
            
            # Continue to next iteration
            continue
        
        elif action == 'create_tool':
            # Create tool and continue loop
            create_result = handle_create_tool(
                parsed_response,
                internal_history
            )
            
            # Continue to next iteration
            continue
        
        else:
            # Unknown action, add to history and let Gemini try again
            logger.warning(f"Unknown action: {action}")
            internal_history.append({
                'role': 'system',
                'content': f"Unknown action '{action}' received. Please choose from: use_tool, search_tools, create_tool, or respond."
            })
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
    """Handle use_tool action"""
    tool_name = parsed_response.get('tool_name')
    parameters = parsed_response.get('parameters', {})
    reasoning = parsed_response.get('reasoning', '')
    
    logger.info(f"Executing tool: {tool_name} with params: {parameters}")
    
    # Add decision to history
    internal_history.append({
        'role': 'assistant',
        'content': f"I will use the tool '{tool_name}' with parameters {json.dumps(parameters)}. Reasoning: {reasoning}"
    })
    
    # Execute tool
    execution_result = execute_tool_with_docker(tool_name, parameters, use_docker)
    
    # Add detailed result to history with better error context
    if execution_result.get('success'):
        result_content = f"""Tool '{tool_name}' executed successfully.
Execution Method: {'Docker Container' if execution_result.get('executed_in_docker') else 'Direct'}
Result: {json.dumps(execution_result.get('result'), indent=2)}

Now use this result to answer the user's query. Do NOT create the tool again."""
    else:
        error_msg = execution_result.get('error', 'Unknown error')
        result_content = f"""Tool '{tool_name}' execution FAILED.
Error: {error_msg}

The tool exists but failed to execute. Possible reasons:
1. The tool has a bug in its implementation
2. Required dependencies are missing
3. Network/API issues
4. Invalid parameters

DO NOT create the tool again. Instead:
- If you can fix the tool, create a CORRECTED version with a different name
- If the error is about missing the tool, search for it first
- If you cannot proceed, explain the error to the user

Error details: {json.dumps(execution_result, indent=2)}"""
    
    internal_history.append({
        'role': 'system',
        'content': result_content
    })
    
    return execution_result

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
        
        result_content = f"""Tool '{tool_name}' created successfully.
File saved to: {filepath}
Tool server reloaded: {reload_success}
You can now use this tool with the 'use_tool' action."""
        
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
            'configured': GEMINI_API_KEY is not None
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