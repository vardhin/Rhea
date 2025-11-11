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
    state: Literal["respond", "create_tool", "use_tool", "exit_response", "fetch_tool"]
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
4. **create_tool**: Create a new tool if none exist for the task
5. **exit_response**: Provide final answer and conclude

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

**COMPOSITE TOOLS - Tool Chaining:**
You can create tools that use OTHER existing tools! This is powerful for:
- Combining multiple operations
- Creating workflows
- Reusing existing functionality

**Inside ANY tool code, you have access to `execute_tool(tool_name, params)` function:**
```python
# Example: Use another tool inside your tool
result1 = execute_tool('calculate_factorial', {'n': params['n']})
result2 = execute_tool('count_characters', {'text': str(result1)})
result = {'factorial': result1, 'length': result2}
```

**Composite Tool Guidelines:**
- Use execute_tool() to call other tools by name
- Pass parameters as dictionaries
- Handle errors with try/except blocks
- Chain multiple tools for complex operations
- Combine results from multiple tools

**Response Format:**
You MUST respond with ONLY valid JSON in this exact structure:
{
  "state": "respond|fetch_tool|use_tool|create_tool|exit_response",
  "reasoning": "Explain your thought process and why you chose this state",
  "action": {
    // State-specific action data
  }
}

**Action Field Requirements by State:**

- **use_tool**: 
  {
    "tool_name": "exact_tool_name",
    "params": {  // MUST use "params", NOT "parameters"
      "param1": "value1",
      "param2": "value2"
    }
  }

- **fetch_tool**:
  {
    "query": "search query string"
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
"""

    def _generate_tool_code_prompt(self, tool_spec: Dict[str, Any]) -> str:
        """Generate a focused prompt for tool code generation"""
        return f"""Generate ONLY executable Python code for the following tool. No explanations, no markdown, just raw Python code.

**Tool Specification:**
- Name: {tool_spec.get('name')}
- Description: {tool_spec.get('description')}
- Category: {tool_spec.get('category')}
- Required Parameters: {tool_spec.get('required_params')}
- Optional Parameters: {tool_spec.get('optional_params')}

**CRITICAL REQUIREMENTS:**
1. Import ALL necessary libraries at the top (requests, json, etc.)
2. Access parameters via `params` dict (e.g., `query = params['query']`)
3. Store the final output in a variable called `result`
4. Use REAL libraries and APIs - NO placeholders or simulations, THE API MUST NOT BE PAID OR FREEMIUM, IT SHOULD BE FULLY FREE IF NOT JUST DO SCRAPING
5. Handle errors with try/except blocks
6. For web searches: Use multiple fallback sources if primary fails
7. Return structured data with meaningful information even if API returns empty
8. Include user-friendly messages when no results are found

**COMPOSITE TOOL CAPABILITY:**
You can call OTHER existing tools using `execute_tool(tool_name, params)`:
```python
# Example 1: Chain tools
fahrenheit = execute_tool('celsius_to_fahrenheit', {{'celsius': params['temp']}})
kelvin = execute_tool('fahrenheit_to_kelvin', {{'fahrenheit': fahrenheit}})
result = kelvin

# Example 2: Combine multiple tools
factorial = execute_tool('calculate_factorial', {{'n': params['n']}})
char_count = execute_tool('count_characters', {{'text': str(factorial)}})
result = {{'factorial': factorial, 'length': char_count}}

# Example 3: Conditional tool usage
if params['operation'] == 'add':
    result = execute_tool('add_numbers', {{'a': params['x'], 'b': params['y']}})
else:
    result = execute_tool('multiply_numbers', {{'a': params['x'], 'b': params['y']}})
```

**When to Use execute_tool():**
- If existing tools can solve part of the problem, USE THEM
- Build on existing functionality rather than reimplementing
- Create workflows by chaining multiple tools
- Handle errors from tool execution with try/except

**Generate the code NOW (code only, no explanation):"""

    def _build_user_prompt(self, context: IterationContext) -> str:
        prompt = f"**Question:** {context.question}\n\n"
        prompt += f"**Iteration:** {context.iteration}/{MAX_ITERATIONS}\n\n"
        
        if context.history:
            prompt += "**Previous Actions:**\n"
            for entry in context.history:
                prompt += f"- {entry['state']}: {entry['reasoning']}\n"
                if 'result' in entry:
                    prompt += f"  Result: {entry['result']}\n"
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
            prompt += "\n"
            
            # Add composite tool hint if multiple tools exist
            if len(context.fetched_tools) > 1:
                prompt += "**Note:** You can create a COMPOSITE TOOL that uses multiple existing tools via execute_tool()!\n\n"
        
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
                # If 'parameters' is used instead of 'params', rename it
                if 'parameters' in action and 'params' not in action:
                    action['params'] = action.pop('parameters')
                # Ensure params exists
                if 'params' not in action:
                    action['params'] = {}
            
            return AgentState(**data)
        except Exception as e:
            print(f"Failed to parse response: {response_text}")
            print(f"Error: {e}")
            return AgentState(
                state="exit_response",
                reasoning=f"Failed to parse response: {str(e)}",
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
            
            context.fetched_tools = tools
            print(f"Found {len(tools)} tools")
            return {"tools_found": len(tools), "tools": [t.get('name', 'Unknown') for t in tools]}
        
        elif state.state == "use_tool":
            tool_name = state.action.get('tool_name')
            params = state.action.get('params', {})
            
            print(f"DEBUG - Full action dict: {state.action}")  # Add this line
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
            
            # Step 1: Generate focused prompt for code generation
            code_prompt = self._generate_tool_code_prompt(state.action)
            
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
                
                print("\n" + "="*60)
                print("Generated Tool Code:")
                print("="*60)
                print(generated_code)
                print("="*60 + "\n")
                
                # Step 3: Validate code
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
                    "generated_code": generated_code
                }
                
            except Exception as e:
                print(f"Failed to create tool: {e}")
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