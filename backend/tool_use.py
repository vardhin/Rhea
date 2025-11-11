from google import genai
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel
import requests
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
GEMINI_MODEL = "gemini-2.5-flash"
TOOL_STORE_URL = "http://localhost:8000"
MAX_ITERATIONS = 10
MIN_REQUEST_INTERVAL = 5.0  # seconds between requests

# State Models
class AgentState(BaseModel):
    state: Literal["respond", "create_tool", "use_tool", "exit_response", "fetch_tool", "analyze_tools_for_composite"]
    reasoning: str
    action: Optional[Dict[str, Any]] = None

class ToolCreation(BaseModel):
    name: str
    description: str
    code: str
    category: str
    required_params: List[str]
    optional_params: Dict[str, Any]
    return_schema: Dict[str, Any]
    examples: List[Dict[str, Any]]
    tags: List[str]

class IterationContext(BaseModel):
    question: str
    iteration: int
    history: List[Dict[str, Any]]
    fetched_tools: List[Dict[str, Any]] = []
    tool_execution_results: List[Dict[str, Any]] = []

# Tool Store API Client
class ToolStoreClient:
    def __init__(self, base_url: str = TOOL_STORE_URL):
        self.base_url = base_url
    
    def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """Search for tools"""
        response = requests.get(f"{self.base_url}/tools/search/{query}")
        if response.status_code == 200:
            return response.json()
        return []
    
    def list_tools(self, active_only: bool = True, exclude_bugged: bool = True) -> List[Dict[str, Any]]:
        """List all available tools"""
        response = requests.get(
            f"{self.base_url}/tools/",
            params={"active_only": active_only, "exclude_bugged": exclude_bugged}
        )
        if response.status_code == 200:
            return response.json()
        return []
    
    def get_tool_details(self, tool_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific tool including its code"""
        response = requests.get(f"{self.base_url}/tools/name/{tool_name}")
        if response.status_code == 200:
            return response.json()
        return {}
    
    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name"""
        response = requests.post(
            f"{self.base_url}/tools/name/{tool_name}/execute",
            json={"params": params}
        )
        return response.json()
    
    def create_tool(self, tool_data: ToolCreation) -> Dict[str, Any]:
        """Create a new tool"""
        response = requests.post(
            f"{self.base_url}/tools/",
            json=tool_data.model_dump()
        )
        if response.status_code != 201:
            raise Exception(f"Failed to create tool: {response.status_code} {response.text}")
        return response.json()

# API Key Manager with Rate Limiting
class GeminiAPIManager:
    def __init__(self, api_keys: List[str]):
        if not api_keys:
            raise ValueError("No API keys provided")
        
        self.api_keys = api_keys
        self.current_index = 0
        self.clients = [genai.Client(api_key=key) for key in api_keys]
        self.last_request_time = 0
        
        print(f"Initialized with {len(api_keys)} API keys")
    
    def _wait_for_rate_limit(self):
        """Ensure minimum time between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - time_since_last
            print(f"Rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        else:
            # Always sleep for at least 4 seconds before any API call
            print(f"Sleeping for {MIN_REQUEST_INTERVAL} seconds before API request...")
            time.sleep(MIN_REQUEST_INTERVAL)
        
        self.last_request_time = time.time()
        
    def _get_next_client(self):
        """Get next client in round-robin fashion"""
        client = self.clients[self.current_index]
        key_number = self.current_index + 1
        self.current_index = (self.current_index + 1) % len(self.clients)
        return client, key_number
    
    def generate_content(self, model: str, contents: str, max_retries: int = None) -> Any:
        """Generate content with automatic retry on overload"""
        if max_retries is None:
            max_retries = len(self.api_keys)
        
        last_error = None
        
        for attempt in range(max_retries):
            self._wait_for_rate_limit()
            
            client, key_number = self._get_next_client()
            
            try:
                print(f"Using API key #{key_number} (attempt {attempt + 1}/{max_retries})")
                response = client.models.generate_content(
                    model=model,
                    contents=contents
                )
                return response
                
            except Exception as e:
                error_msg = str(e).lower()
                last_error = e
                
                if any(keyword in error_msg for keyword in ['overload', 'quota', 'rate limit', '429', '503']):
                    print(f"API key #{key_number} overloaded: {e}")
                    if attempt < max_retries - 1:
                        print(f"Switching to next API key...")
                        continue
                else:
                    raise e
        
        raise Exception(f"All {max_retries} API keys failed. Last error: {last_error}")

# Gemini Agent
class ToolUseAgent:
    def __init__(self, api_keys: List[str]):
        self.api_manager = GeminiAPIManager(api_keys)
        self.tool_store = ToolStoreClient()
    
    def _build_system_prompt(self) -> str:
        return """You are an AI assistant with access to a tool system. You can perform these actions:

**States:**
1. **respond**: Directly answer if you can with high confidence
2. **fetch_tool**: Search for tools that can help answer the question
3. **use_tool**: Execute a specific tool with parameters
4. **create_tool**: Create a new tool ONLY as a last resort
5. **exit_response**: Provide final answer and conclude
6. **analyze_tools_for_composite**: Fetch detailed information about specific tools before creating a composite tool

**🎯 TOOL USAGE PHILOSOPHY - READ CAREFULLY:**

**ALWAYS PREFER EXISTING TOOLS OVER CREATING NEW ONES**
- If a tool exists that does 80% of what you need, USE IT
- Create composite tools that wrap/combine existing tools
- Only create entirely new tools if NO existing tools can help

**DECISION TREE FOR TOOL USAGE:**
1. **First**: Search for existing tools (fetch_tool)
2. **Second**: Can you use an existing tool directly? → use_tool
3. **Third**: Can you create a simple composite tool that calls existing tools? → analyze_tools_for_composite → create_tool (composite)
4. **Last Resort**: Create a brand new tool with new implementation

**COMPOSITE TOOLS ARE YOUR FRIEND:**
- If you need to chain operations, create a composite tool
- If you need to combine results, create a composite tool
- If you need to transform output of one tool for another, create a composite tool
- Composite tools are MUCH better than reinventing functionality

**Example Scenarios:**

❌ **WRONG**: "I need to search news and summarize. Let me create a new tool that scrapes news websites..."
✅ **RIGHT**: "I found a 'web_search' tool. Let me create a composite tool that calls web_search and formats results."

❌ **WRONG**: "I need temperature conversion with logging. Let me implement temperature conversion from scratch..."
✅ **RIGHT**: "I found 'fahrenheit_to_celsius' tool. Let me create a composite that calls it and adds logging."

**CRITICAL: Analyzing Tool Results:**
- When tools return search results or scraped content, ANALYZE and EXTRACT the relevant information
- Don't mark results as "empty" just because they need parsing
- Look for news headlines, article content, dates, and relevant details in the returned data
- If you get URLs or titles, that IS useful information - extract and present it
- Only mark as truly empty if the result is literally "[]", "{}", or an error

**Tool Usage Guidelines:**
- Parse JSON strings and extract meaningful data
- Summarize news articles and search results
- If multiple URLs are returned, mention the most relevant ones

**CRITICAL: Tool Creation Rule:**
- If fetch_tool finds NO tools or NO APPROPRIATE tools, you MUST immediately transition to create_tool state
- Do NOT exit or respond without creating a tool when none exist for the task

**COMPOSITE TOOLS - MANDATORY WORKFLOW:**
Before creating ANY tool, you MUST:
1. Use **fetch_tool** state to find existing tools
2. **EVALUATE**: Can I use these tools directly? Can I compose them?
3. If composition needed: Use **analyze_tools_for_composite** state
4. Create a SIMPLE wrapper that calls existing tools
5. ONLY create new implementation if truly no existing tools can help

**Inside ANY tool code, you have access to `execute_tool(tool_name, params)` function:**
```python
# Example 1: Simple wrapper
search_results = execute_tool('web_search', {'query': params['query']})
result = {'results': search_results, 'count': len(search_results)}

# Example 2: Chain existing tools
raw_data = execute_tool('fetch_data', {'url': params['url']})
cleaned = execute_tool('clean_text', {'text': raw_data})
result = cleaned

# Example 3: Combine multiple existing tools
temp_c = execute_tool('fahrenheit_to_celsius', {'fahrenheit': params['temp']})
temp_k = execute_tool('celsius_to_kelvin', {'celsius': temp_c})
result = {'celsius': temp_c, 'kelvin': temp_k}
```

**⚠️ BEFORE CREATING A TOOL, ASK YOURSELF:**
1. "Did I search for existing tools?" (If no → fetch_tool first)
2. "Can I use an existing tool directly?" (If yes → use_tool)
3. "Can I combine existing tools?" (If yes → analyze_tools_for_composite)
4. "Do I REALLY need new implementation?" (Last resort only)

**Response Format:**
You MUST respond with ONLY valid JSON in this exact structure:
{
  "state": "respond|fetch_tool|use_tool|create_tool|exit_response|analyze_tools_for_composite",
  "reasoning": "Explain your thought process and why you chose this state",
  "action": {
    // State-specific action data
  }
}

**Action Field Requirements by State:**

- **use_tool**: 
  {
    "tool_name": "exact_tool_name",
    "params": {
      "param1": "value1",
      "param2": "value2"
    }
  }

- **fetch_tool**:
  {
    "query": "search query string"
  }

- **analyze_tools_for_composite**:
  {
    "tool_names": ["tool_name1", "tool_name2"]
  }

- **create_tool**:
  {
    "name": "tool_name",
    "description": "what it does",
    "category": "category",
    "required_params": ["param1", "param2"],
    "optional_params": {},
    "return_schema": {},
    "examples": [],
    "tags": []
  }

- **respond** or **exit_response**:
  {
    "final_answer": "your answer here",
    "confidence": "high|medium|low"
  }

**CRITICAL**: 
- Use "reasoning" field, NOT "response" field
- Use "params" field for tool parameters, NOT "parameters"
- ALWAYS use analyze_tools_for_composite before creating composite tools
"""

    def _generate_tool_code_prompt(self, tool_spec: Dict[str, Any], available_tools: List[Dict[str, Any]] = None) -> str:
        """Generate a focused prompt for tool code generation"""
        
        # Build available tools section
        tools_context = ""
        if available_tools:
            tools_context = "\n**AVAILABLE EXISTING TOOLS YOU MUST USE:**\n"
            for tool in available_tools:
                tools_context += f"- `{tool.get('name')}`: {tool.get('description')}\n"
                tools_context += f"  Params: {tool.get('required_params', [])}\n"
                if 'code' in tool:
                    tools_context += f"  Implementation: {tool['code'][:200]}...\n"
            tools_context += "\n**YOU MUST CALL THESE TOOLS USING execute_tool() - DO NOT REIMPLEMENT!**\n\n"
        
        return f"""Generate ONLY executable Python code for the following tool. No explanations, no markdown, just raw Python code.

**Tool Specification:**
- Name: {tool_spec.get('name')}
- Description: {tool_spec.get('description')}
- Category: {tool_spec.get('category')}
- Required Parameters: {tool_spec.get('required_params')}
- Optional Parameters: {tool_spec.get('optional_params')}

{tools_context}

**CRITICAL REQUIREMENTS:**
1. **MANDATORY**: If ANY existing tools are listed above, you MUST use `execute_tool(tool_name, params)` to call them
2. **DO NOT reimplement** functionality that existing tools already provide
3. Access parameters via `params` dict (e.g., `query = params['query']`)
4. Store the final output in a variable called `result`
5. Handle errors with try/except blocks when calling execute_tool()

**COMPOSITE TOOL RULES - EXTREMELY IMPORTANT:**
If this tool's description mentions or implies using existing functionality:
- **STEP 1**: Call the existing tool(s) using execute_tool()
- **STEP 2**: Process/format the result if needed
- **STEP 3**: Return the processed result

**DO THIS (Composite Tool Pattern):**
```python
# Example: Search and format tool
try:
    # Call existing tool
    search_data = execute_tool('web_search', {{'query': params['query'], 'max_results': params.get('max_results', 5)}})
    
    # Process the result
    if search_data.get('success'):
        results = search_data.get('result', {{}})
        formatted = {{
            'query': params['query'],
            'total_results': len(results.get('items', [])),
            'top_results': results.get('items', [])[:3]
        }}
        result = formatted
    else:
        result = {{'error': 'Search failed', 'details': search_data.get('error')}}
except Exception as e:
    result = {{'error': str(e), 'success': False}}
```

**DO THIS (Chain Multiple Tools):**
```python
# Example: Multi-step tool
try:
    # Step 1: Fetch data
    data = execute_tool('fetch_web_content', {{'url': params['url']}})
    
    # Step 2: Process with another tool
    if data.get('success'):
        processed = execute_tool('extract_text', {{'html': data['result']}})
        result = processed.get('result')
    else:
        result = {{'error': 'Failed to fetch', 'details': data}}
except Exception as e:
    result = {{'error': str(e)}}
```

**DO NOT DO THIS (Reimplementing):**
```python
# ❌ WRONG - Reimplementing search functionality
import requests
response = requests.get('https://api.search.com/...')  # NO! Use execute_tool() instead!
```

**When to Use execute_tool():**
- **ALWAYS** when existing tools can do part of the work
- To chain operations: tool1 → tool2 → tool3
- To combine results from multiple tools
- To add validation/formatting around existing tool output

**When to Write New Code:**
- Only for formatting/processing tool results
- Only for orchestration logic between tools
- NEVER for reimplementing existing functionality

**Generate the code NOW (code only, no explanation):"""

    def _build_user_prompt(self, context: IterationContext) -> str:
        prompt = f"**Question:** {context.question}\n\n"
        prompt += f"**Iteration:** {context.iteration}/{MAX_ITERATIONS}\n\n"
        
        if context.history:
            prompt += "**Previous Actions:**\n"
            for entry in context.history:
                prompt += f"- {entry['state']}: {entry['reasoning']}\n"
                if 'result' in entry:
                    result_preview = str(entry['result'])[:200]
                    prompt += f"  Result: {result_preview}...\n" if len(str(entry['result'])) > 200 else f"  Result: {entry['result']}\n"
            prompt += "\n"
        
        if context.fetched_tools:
            prompt += "**Available Tools:**\n"
            for tool in context.fetched_tools:
                name = tool.get('name', 'Unknown')
                description = tool.get('description', 'No description')
                required_params = tool.get('required_params', [])
                optional_params = tool.get('optional_params', {})
                
                prompt += f"- **{name}**: {description}\n"
                prompt += f"  Required params: {required_params}\n"
                prompt += f"  Optional params: {optional_params}\n"
                
                # Show detailed code if available (from analyze_tools_for_composite)
                if 'code' in tool:
                    prompt += f"  Code preview: {tool['code'][:150]}...\n"
                if 'return_schema' in tool:
                    prompt += f"  Returns: {tool['return_schema']}\n"
            prompt += "\n"
            
            # Add composite tool hint only if tools are fetched but NOT analyzed
            if len(context.fetched_tools) > 1:
                has_detailed_info = any('code' in tool for tool in context.fetched_tools)
                if not has_detailed_info:
                    prompt += "**⚠️ IMPORTANT:** To create a composite tool, first use 'analyze_tools_for_composite' state to fetch detailed tool information!\n\n"
                else:
                    prompt += "**✓ Tool details available:** You can now create a composite tool using the analyzed information.\n\n"
        
        if context.tool_execution_results:
            prompt += "**Tool Execution Results:**\n"
            for result in context.tool_execution_results:
                prompt += f"- Tool: {result['tool_name']}\n"
                prompt += f"  Success: {result['success']}\n"
                prompt += f"  Result: {result.get('result')}\n"
                if result.get('error'):
                    prompt += f"  Error: {result['error']}\n"
            prompt += "\n"
        
        prompt += "**Your Response (JSON only):**"
        return prompt
    
    def _parse_gemini_response(self, response_text: str) -> AgentState:
        """Parse Gemini's JSON response"""
        try:
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            # Try to find JSON object boundaries if surrounded by text
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start != -1 and json_end != -1:
                text = text[json_start:json_end + 1]
            
            data = json.loads(text)
            
            # Handle common field name variations
            if 'response' in data and 'reasoning' not in data:
                data['reasoning'] = data.pop('response')
            
            # Ensure required fields exist
            if 'reasoning' not in data:
                data['reasoning'] = data.get('action', {}).get('answer', 'No reasoning provided')
            
            # Normalize parameter field name for use_tool state
            if data.get('state') == 'use_tool' and data.get('action'):
                action = data['action']
                if 'parameters' in action and 'params' not in action:
                    action['params'] = action.pop('parameters')
                if 'params' not in action:
                    action['params'] = {}
            
            # Validate and clean tool creation code
            if data.get('state') == 'create_tool' and data.get('action', {}).get('code'):
                # Ensure code doesn't break JSON serialization
                code = data['action']['code']
                # Remove any null bytes or control characters
                code = ''.join(char for char in code if ord(char) >= 32 or char in '\n\r\t')
                data['action']['code'] = code
            
            return AgentState(**data)
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error at line {e.lineno}, col {e.colno}")
            print(f"Failed to parse response (first 500 chars):\n{response_text[:500]}")
            print(f"Error: {e}")
            
            # Try to extract reasoning if present
            reasoning = "Failed to parse JSON response"
            if "reasoning" in response_text:
                try:
                    reasoning_match = re.search(r'"reasoning":\s*"([^"]*(?:\\.[^"]*)*)"', response_text)
                    if reasoning_match:
                        reasoning = reasoning_match.group(1)
                except:
                    pass
            
            return AgentState(
                state="exit_response",
                reasoning=reasoning,
                action={"final_answer": f"JSON parsing error: {str(e)}", "confidence": "low"}
            )
        except Exception as e:
            print(f"Unexpected error parsing response: {response_text}")
            print(f"Error: {e}")
            return AgentState(
                state="exit_response",
                reasoning=f"Unexpected parsing error: {str(e)}",
                action={"final_answer": "Error in processing", "confidence": "low"}
            )
    
    def process_question(self, question: str) -> Dict[str, Any]:
        """Process a question through iterative tool use"""
        context = IterationContext(question=question, iteration=0, history=[])
        
        system_prompt = self._build_system_prompt()
        
        for i in range(MAX_ITERATIONS):
            context.iteration = i + 1
            
            print(f"\n{'='*60}")
            print(f"ITERATION {context.iteration}")
            print(f"{'='*60}")
            
            user_prompt = self._build_user_prompt(context)
            
            try:
                response = self.api_manager.generate_content(
                    model=GEMINI_MODEL,
                    contents=f"{system_prompt}\n\n{user_prompt}"
                )
                
                response_text = response.text
                print(f"\nGemini Response:\n{response_text}\n")
                
            except Exception as e:
                print(f"Gemini API Error (all keys failed): {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "iterations": context.iteration
                }
            
            agent_state = self._parse_gemini_response(response_text)
            
            print(f"State: {agent_state.state}")
            print(f"Reasoning: {agent_state.reasoning}")
            
            result = self._execute_state(agent_state, context)
            
            context.history.append({
                "state": agent_state.state,
                "reasoning": agent_state.reasoning,
                "action": agent_state.action,
                "result": result
            })
            
            if agent_state.state == "exit_response":
                print(f"\n{'='*60}")
                print("FINAL ANSWER")
                print(f"{'='*60}")
                print(f"Answer: {agent_state.action.get('final_answer')}")
                print(f"Confidence: {agent_state.action.get('confidence')}")
                
                return {
                    "success": True,
                    "answer": agent_state.action.get('final_answer'),
                    "confidence": agent_state.action.get('confidence'),
                    "iterations": context.iteration,
                    "history": context.history
                }
        
        return {
            "success": False,
            "error": "Maximum iterations reached",
            "iterations": context.iteration,
            "history": context.history
        }
    
    def _execute_state(self, state: AgentState, context: IterationContext) -> Any:
        """Execute the action for the current state"""
        
        if state.state == "respond":
            return {"direct_answer": state.action.get('answer')}
        
        elif state.state == "fetch_tool":
            query = state.action.get('query', '')
            print(f"Fetching tools with query: {query}")
            
            if query:
                tools = self.tool_store.search_tools(query)
            else:
                tools = self.tool_store.list_tools()
            
            # Store basic tool info (without code details)
            context.fetched_tools = tools
            print(f"Found {len(tools)} tools")
            return {"tools_found": len(tools), "tools": [t.get('name', 'Unknown') for t in tools]}
        
        elif state.state == "analyze_tools_for_composite":
            tool_names = state.action.get('tool_names', [])
            print(f"Analyzing tools for composite: {tool_names}")
            
            detailed_tools = []
            for tool_name in tool_names:
                tool_details = self.tool_store.get_tool_details(tool_name)
                if tool_details:
                    detailed_tools.append(tool_details)
                    print(f"✓ Fetched details for: {tool_name}")
                else:
                    print(f"✗ Could not fetch details for: {tool_name}")
            
            # Replace fetched_tools with detailed versions
            context.fetched_tools = detailed_tools
            
            return {
                "success": True,
                "analyzed_count": len(detailed_tools),
                "tool_names": [t.get('name') for t in detailed_tools],
                "details": "Full tool details including code, params, and return schemas fetched"
            }
        
        elif state.state == "use_tool":
            tool_name = state.action.get('tool_name')
            params = state.action.get('params', {})
            
            print(f"DEBUG - Full action dict: {state.action}")
            print(f"Executing tool: {tool_name} with params: {params}")
            
            result = self.tool_store.execute_tool(tool_name, params)
            
            # Handle bugged tool response
            if 'detail' in result and 'bugged' in result.get('detail', '').lower():
                result = {
                    'success': False,
                    'error': result.get('detail', 'Tool is marked as bugged'),
                    'result': None
                }
            
            # Check for empty/meaningless results only if successful
            if result.get('success') and result.get('result'):
                tool_result = result.get('result', {})
                if isinstance(tool_result, dict):
                    data = tool_result.get('data', {})
                    # Check if data is effectively empty
                    if isinstance(data, dict):
                        has_content = any([
                            data.get('abstract_text'),
                            data.get('answer'),
                            data.get('results'),
                            data.get('related_topics')
                        ])
                        if not has_content:
                            result['empty_results'] = True
                            result['message'] = 'Tool returned no meaningful data. Consider alternative approaches.'
        
            context.tool_execution_results.append({
                "tool_name": tool_name,
                "params": params,
                **result
            })
            
            print(f"Tool execution result: {result}")
            return result
        
        elif state.state == "create_tool":
            print(f"Creating new tool: {state.action.get('name')}")
            
            # 🔍 VALIDATION: Ensure existing tools were considered
            if not context.fetched_tools:
                print("⛔ BLOCKING: Cannot create tool without first searching for existing tools!")
                return {
                    "error": "You must use 'fetch_tool' state before creating a new tool",
                    "success": False,
                    "message": "Always search for existing tools first. You might find tools you can reuse or compose."
                }
            
            # Check if this could use existing tools instead
            tool_desc = state.action.get('description', '').lower()
            existing_tool_names = [t.get('name', '') for t in context.fetched_tools]
            
            if existing_tool_names and len(existing_tool_names) > 0:
                print(f"⚠️ NOTE: {len(existing_tool_names)} existing tools available: {existing_tool_names}")
                print("Consider creating a composite tool that uses these instead of reimplementing.")
            
            # Validate: If this might be a composite tool, ensure tools were analyzed
            if context.fetched_tools:
                has_detailed_info = any('code' in tool for tool in context.fetched_tools)
                tool_desc = state.action.get('description', '').lower()
                seems_composite = any(keyword in tool_desc for keyword in ['combine', 'chain', 'multiple', 'using', 'execute_tool', 'search', 'fetch', 'get'])
                
                if seems_composite and not has_detailed_info:
                    print("⚠️ WARNING: Attempting to create composite tool without analyzing tool details!")
                    return {
                        "error": "Cannot create composite tool without first using 'analyze_tools_for_composite' state",
                        "success": False,
                        "message": "Use analyze_tools_for_composite to fetch tool details before creating composite tools"
                    }
            
            # Sanitize tool action data before sending to Gemini
            sanitized_action = state.action.copy()
            
            # Step 1: Generate focused prompt for code generation WITH available tools context
            code_prompt = self._generate_tool_code_prompt(sanitized_action, context.fetched_tools)
            
            print("\n" + "="*60)
            print("Requesting tool code from Gemini...")
            print("="*60)
            
            try:
                # Step 2: Send isolated request to Gemini for code only
                code_response = self.api_manager.generate_content(
                    model=GEMINI_MODEL,
                    contents=code_prompt
                )
                
                generated_code = code_response.text.strip()
                
                # Clean up markdown code blocks if present
                if generated_code.startswith("```python"):
                    generated_code = generated_code[9:]
                elif generated_code.startswith("```"):
                    generated_code = generated_code[3:]
                if generated_code.endswith("```"):
                    generated_code = generated_code[:-3]
                generated_code = generated_code.strip()
                
                # Remove any problematic characters for JSON serialization
                generated_code = generated_code.replace('\x00', '')
                
                print("\n" + "="*60)
                print("Generated Tool Code:")
                print("="*60)
                print(generated_code)
                print("="*60 + "\n")
                
                # Step 3: Validate code - CHECK FOR execute_tool() usage
                forbidden_patterns = [
                    'placeholder',
                    'simulated',
                    'mock',
                    'dummy',
                    'fake',
                    'TODO',
                    'not implemented',
                    'pass  # implementation'
                ]
                
                code_lower = generated_code.lower()
                if any(pattern in code_lower for pattern in forbidden_patterns):
                    print(f"REJECTED: Tool code contains placeholder patterns")
                    return {
                        "error": "Generated code contains placeholders. Tool must have real implementation.",
                        "success": False,
                        "generated_code": generated_code
                    }
                
                # NEW VALIDATION: Check if composite tool should use execute_tool()
                if context.fetched_tools and len(context.fetched_tools) > 0:
                    has_execute_tool = 'execute_tool(' in generated_code
                    seems_composite = any(keyword in tool_desc for keyword in ['search', 'fetch', 'get', 'find', 'retrieve'])
                    
                    if seems_composite and not has_execute_tool:
                        print("⚠️ REJECTED: Tool should use existing tools via execute_tool() but doesn't!")
                        existing_names = [t.get('name', 'unknown') for t in context.fetched_tools]
                        return {
                            "error": f"This tool should call existing tools {existing_names} using execute_tool(), but the generated code doesn't use it. REIMPLEMENT AS COMPOSITE TOOL.",
                            "success": False,
                            "generated_code": generated_code,
                            "suggestion": f"The code should call execute_tool('{existing_names[0]}', params) instead of reimplementing."
                        }
                
                # Step 4: Ensure result variable exists
                if 'result =' not in generated_code and 'result=' not in generated_code:
                    print("Warning: Code doesn't assign to 'result'. Adding wrapper...")
                    if 'def ' in generated_code:
                        func_name = generated_code.split('def ')[1].split('(')[0].strip()
                        generated_code = f"{generated_code}\nresult = {func_name}(params)"
                    else:
                        generated_code = f"result = {generated_code}"
                
                # Step 5: Create tool with generated code
                state.action['code'] = generated_code
                
                tool_data = ToolCreation(**state.action)
                result = self.tool_store.create_tool(tool_data)
                
                context.fetched_tools.append(result)
                
                print(f"\n✓ Tool created successfully: {result.get('name')} (ID: {result.get('id')})")
                return {
                    "success": True,
                    "tool_id": result.get('id'),
                    "tool_name": result.get('name'),
                    "generated_code": generated_code[:200] + "..." if len(generated_code) > 200 else generated_code
                }
                
            except Exception as e:
                import traceback
                print(f"Failed to create tool: {e}")
                print(f"Full traceback: {traceback.format_exc()}")
                return {"error": str(e), "success": False}
        
        elif state.state == "exit_response":
            return {"final_answer": state.action.get('final_answer')}
        
        return None

# Main execution
def main():
    api_keys = []
    for i in range(1, 8):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            api_keys.append(key)
    
    if not api_keys:
        print("No API keys found! Please set GEMINI_API_KEY_1 to GEMINI_API_KEY_7")
        return
    
    print(f"Loaded {len(api_keys)} API keys")
    
    agent = ToolUseAgent(api_keys)
    
    questions = [
        "How many 'x' characters are in the word 'xylophone'?",
        "What is 15 factorial?",
        "Convert 100 degrees Fahrenheit to Celsius"
    ]
    
    for question in questions:
        print(f"\n\n{'#'*70}")
        print(f"# Question: {question}")
        print(f"{'#'*70}")
        
        result = agent.process_question(question)
        
        print(f"\n{'='*70}")
        print("FINAL RESULT:")
        print(json.dumps(result, indent=2))
        print(f"{'='*70}\n")

if __name__ == "__main__":
    main()