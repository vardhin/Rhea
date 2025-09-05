import ollama
from ollama import Client, AsyncClient
from typing import List, Dict, Any, Optional, Union, Generator, AsyncGenerator
import json
import logging

logger = logging.getLogger(__name__)

class OllamaManager:
    """
    A comprehensive manager class for interacting with Ollama server.
    Supports both sync and async operations, including gpt-oss specific features.
    """
    
    def __init__(self, host: str = "http://localhost:11434", api_key: str = "ollama"):
        """
        Initialize the Ollama manager.
        
        Args:
            host: Ollama server URL (default: localhost:11434)
            api_key: API key for authentication (default: "ollama")
        """
        self.host = host
        self.api_key = api_key
        self.client = Client(host=host)
        self.async_client = AsyncClient(host=host)
        self.current_model = None
        self.thinking_mode = False
        self.reasoning_level = "medium"  # low, medium, high for gpt-oss
        self.available_tools = {}  # Store available tools
        self.selected_tools = []   # Store currently selected tools
        
        # Initialize with default tools
        self._initialize_default_tools()
        
    def _initialize_default_tools(self):
        """Initialize default available tools"""
        self.available_tools = {
            "weather": create_weather_tool(),
            "calculator": create_calculator_tool(),
            "web_search": create_web_search_tool(),
            "code_executor": create_code_executor_tool(),
            "file_reader": create_file_reader_tool(),
            "date_time": create_datetime_tool(),
        }

    def get_available_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all available tools.
        
        Returns:
            Dictionary of tool_name -> tool_definition
        """
        return self.available_tools.copy()
    
    def list_tool_names(self) -> List[str]:
        """
        Get list of available tool names.
        
        Returns:
            List of tool names
        """
        return list(self.available_tools.keys())
    
    def add_tool(self, name: str, tool_definition: Dict[str, Any]) -> bool:
        """
        Add a custom tool to available tools.
        
        Args:
            name: Name for the tool
            tool_definition: Tool definition following OpenAI function calling format
            
        Returns:
            True if tool was added successfully
        """
        try:
            # Validate tool definition
            if not self._validate_tool_definition(tool_definition):
                logger.error(f"Invalid tool definition for {name}")
                return False
                
            self.available_tools[name] = tool_definition
            logger.info(f"Added tool: {name}")
            return True
        except Exception as e:
            logger.error(f"Error adding tool {name}: {e}")
            return False
    
    def remove_tool(self, name: str) -> bool:
        """
        Remove a tool from available tools.
        
        Args:
            name: Name of the tool to remove
            
        Returns:
            True if tool was removed successfully
        """
        if name in self.available_tools:
            del self.available_tools[name]
            # Also remove from selected tools if present
            self.selected_tools = [tool for tool in self.selected_tools if tool.get('function', {}).get('name') != name]
            logger.info(f"Removed tool: {name}")
            return True
        else:
            logger.error(f"Tool {name} not found")
            return False
    
    def select_tools(self, tool_names: List[str]) -> bool:
        """
        Select tools to use in chat/generation.
        
        Args:
            tool_names: List of tool names to select
            
        Returns:
            True if all tools were selected successfully
        """
        selected = []
        missing_tools = []
        
        for name in tool_names:
            if name in self.available_tools:
                selected.append(self.available_tools[name])
            else:
                missing_tools.append(name)
        
        if missing_tools:
            logger.error(f"Tools not found: {missing_tools}")
            logger.info(f"Available tools: {self.list_tool_names()}")
            return False
        
        self.selected_tools = selected
        logger.info(f"Selected tools: {tool_names}")
        return True
    
    def get_selected_tools(self) -> List[Dict[str, Any]]:
        """
        Get currently selected tools.
        
        Returns:
            List of selected tool definitions
        """
        return self.selected_tools.copy()
    
    def get_selected_tool_names(self) -> List[str]:
        """
        Get names of currently selected tools.
        
        Returns:
            List of selected tool names
        """
        return [tool.get('function', {}).get('name', '') for tool in self.selected_tools]
    
    def clear_selected_tools(self):
        """Clear all selected tools"""
        self.selected_tools = []
        logger.info("Cleared selected tools")
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool definition or None if not found
        """
        return self.available_tools.get(tool_name)
    
    def _validate_tool_definition(self, tool_def: Dict[str, Any]) -> bool:
        """
        Validate tool definition format.
        
        Args:
            tool_def: Tool definition to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            if tool_def.get("type") != "function":
                return False
                
            function = tool_def.get("function", {})
            if not function.get("name") or not function.get("description"):
                return False
                
            # Check parameters structure
            params = function.get("parameters", {})
            if params.get("type") != "object":
                return False
                
            return True
        except Exception:
            return False

    def chat(
        self, 
        messages: List[Dict[str, str]], 
        stream: bool = False,
        system_message: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        use_selected_tools: bool = True
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Chat with the selected model.
        
        Args:
            messages: List of message dictionaries
            stream: Whether to stream the response
            system_message: Custom system message
            tools: Specific tools to use (overrides selected tools)
            use_selected_tools: Whether to use selected tools if no tools specified
            
        Returns:
            Chat response or stream generator
        """
        if not self.current_model:
            raise ValueError("No model selected. Use select_model() first.")
        
        # Add system message if provided or for gpt-oss models
        if system_message or (self.current_model and 'gpt-oss' in self.current_model):
            system_msg = {"role": "system", "content": self._build_system_message(system_message)}
            if not any(msg.get('role') == 'system' for msg in messages):
                messages = [system_msg] + messages

        try:
            kwargs = {
                'model': self.current_model,
                'messages': messages,
                'stream': stream
            }
            
            # Determine which tools to use
            tools_to_use = tools
            if not tools_to_use and use_selected_tools and self.selected_tools:
                tools_to_use = self.selected_tools

            # Special handling for gpt-oss models with tools - skip automatic parsing
            if (tools_to_use and self.current_model and 'gpt-oss' in self.current_model):
                # For GPT-OSS: Always do manual parsing, never rely on automatic parsing
                kwargs['tools'] = tools_to_use
                
                # Add thinking mode for gpt-oss models
                if self.thinking_mode:
                    kwargs['think'] = self.reasoning_level
            
                try:
                    response = self.client.chat(**kwargs)
                    return response
                except Exception as e:
                    error_msg = str(e)
                    # Skip the automatic parsing check - go straight to manual parsing
                    if "error parsing tool call" in error_msg and "raw='" in error_msg:
                        logger.info("GPT-OSS detected, using manual parsing")
                        
                        # Extract raw response from error message
                        raw_response = error_msg.split("raw='")[1].split("'")[0]
                        cleaned_response = self._clean_tool_response(raw_response)
                        
                        # Try to parse the cleaned response as a tool call
                        parsed_tool_call = self._parse_gpt_oss_tool_call(cleaned_response)
                        if parsed_tool_call:
                            # Create a proper response structure
                            return {
                                'message': {
                                    'role': 'assistant',
                                    'content': '',
                                    'tool_calls': [parsed_tool_call]
                                }
                            }
                        else:
                            # If we can't parse as tool call, return as regular response
                            return {
                                'message': {
                                    'role': 'assistant',
                                    'content': cleaned_response
                                }
                            }
                    else:
                        raise
            else:
                # Non-gpt-oss models or no tools - normal handling
                if tools_to_use:
                    kwargs['tools'] = tools_to_use
            
                # Add thinking mode for gpt-oss models
                if self.current_model and 'gpt-oss' in self.current_model and self.thinking_mode:
                    kwargs['think'] = self.reasoning_level
            
                response = self.client.chat(**kwargs)
                return response
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            raise

    async def chat_async(
        self, 
        messages: List[Dict[str, str]], 
        stream: bool = False,
        system_message: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        use_selected_tools: bool = True
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """Async version of chat method"""
        if not self.current_model:
            raise ValueError("No model selected. Use select_model() first.")
        
        if system_message or (self.current_model and 'gpt-oss' in self.current_model):
            system_msg = {"role": "system", "content": self._build_system_message(system_message)}
            if not any(msg.get('role') == 'system' for msg in messages):
                messages = [system_msg] + messages
        
        try:
            kwargs = {
                'model': self.current_model,
                'messages': messages,
                'stream': stream
            }
            
            # Determine which tools to use
            tools_to_use = tools
            if not tools_to_use and use_selected_tools and self.selected_tools:
                tools_to_use = self.selected_tools
            
            if tools_to_use:
                kwargs['tools'] = tools_to_use
                
            if self.current_model and 'gpt-oss' in self.current_model and self.thinking_mode:
                kwargs['think'] = self.reasoning_level
                
            response = await self.async_client.chat(**kwargs)
            
            # Process tool calls in the response
            if 'tool_calls' in response.get('message', {}):
                for tool_call in response['message']['tool_calls']:
                    if 'function' in tool_call and 'arguments' in tool_call['function']:
                        # Clean the arguments before parsing
                        raw_args = tool_call['function']['arguments']
                        if isinstance(raw_args, str):
                            cleaned_args = self._clean_tool_response(raw_args)
                            try:
                                tool_call['function']['arguments'] = json.loads(cleaned_args)
                            except json.JSONDecodeError:
                                # If still can't parse, keep original
                                pass
            
            return response
            
        except Exception as e:
            logger.error(f"Error in async chat: {e}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model and settings.
        
        Returns:
            Dictionary with current model info and settings
        """
        return {
            'current_model': self.current_model,
            'thinking_mode': self.thinking_mode,
            'reasoning_level': self.reasoning_level,
            'server_host': self.host,
            'is_gpt_oss': self.is_gpt_oss_model(),
            'available_tools': self.list_tool_names(),
            'selected_tools': self.get_selected_tool_names()
        }

    def set_server_url(self, host: str):
        """Change the Ollama server URL"""
        self.host = host
        self.client = Client(host=host)
        self.async_client = AsyncClient(host=host)
        
    def list_models(self) -> List[Dict[str, Any]]:
        """
        List all available models on the Ollama server.
        
        Returns:
            List of model dictionaries with model information
        """
        try:
            response = self.client.list()
            models = response.get('models', [])
            
            # Process the models list
            model_list = []
            for model in models:
                try:
                    model_dict = {}
                    
                    if isinstance(model, dict):
                        # Direct dictionary - use as is
                        model_dict = model.copy()
                    else:
                        # Object with attributes - extract them
                        # Try common attributes that Ollama model objects have
                        for attr in ['name', 'model', 'modified_at', 'size', 'digest', 'details']:
                            if hasattr(model, attr):
                                value = getattr(model, attr)
                                # Handle datetime objects
                                if hasattr(value, 'isoformat'):
                                    model_dict[attr] = value.isoformat()
                                elif hasattr(value, '__dict__'):
                                    # Handle nested objects (like details)
                                    model_dict[attr] = value.__dict__ if hasattr(value, '__dict__') else str(value)
                                else:
                                    model_dict[attr] = value
                
                    # Ensure we have at least a name field
                    if not model_dict.get('name'):
                        # Try different ways to get the model name
                        if hasattr(model, 'name'):
                            model_dict['name'] = str(model.name)
                        elif hasattr(model, 'model'):
                            model_dict['name'] = str(model.model)
                        elif isinstance(model, dict) and 'name' in model:
                            model_dict['name'] = model['name']
                        elif isinstance(model, dict) and 'model' in model:
                            model_dict['name'] = model['model']
                        else:
                            model_dict['name'] = str(model)
                
                    # Add the processed model to our list
                    if model_dict:
                        model_list.append(model_dict)
                        
                except Exception as model_error:
                    logger.warning(f"Error processing individual model: {model_error}")
                    # Last resort - try to extract just the string representation
                    try:
                        fallback_dict = {'name': str(model)}
                        if hasattr(model, 'size'):
                            fallback_dict['size'] = getattr(model, 'size')
                        if hasattr(model, 'modified_at'):
                            modified = getattr(model, 'modified_at')
                            fallback_dict['modified_at'] = modified.isoformat() if hasattr(modified, 'isoformat') else str(modified)
                        model_list.append(fallback_dict)
                    except Exception:
                        logger.error(f"Failed to process model completely: {model}")
                        model_list.append({'name': 'Unknown'})
        
            logger.info(f"Found {len(model_list)} models")
            for model in model_list:
                logger.debug(f"Model: {model.get('name', 'Unknown')} - {model}")
        
            return model_list
        
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []

    def select_model(self, model_name: str) -> bool:
        """
        Select a model to use for chat/generation.
        
        Args:
            model_name: Name of the model to select
            
        Returns:
            True if model exists and is selected, False otherwise
        """
        try:
            models = self.list_models()
            available_models = set()
            
            for model in models:
                # Get both 'name' and 'model' fields as they might be the same
                name = model.get('name', '')
                model_field = model.get('model', '')
                
                if name:
                    available_models.add(name)
                if model_field and model_field != name:
                    available_models.add(model_field)
        
            logger.info(f"Available models: {sorted(available_models)}")
            
            if model_name in available_models:
                self.current_model = model_name
                logger.info(f"Selected model: {model_name}")
                return True
            else:
                logger.error(f"Model '{model_name}' not found")
                logger.info(f"Available models: {sorted(available_models)}")
                return False
            
        except Exception as e:
            logger.error(f"Error selecting model: {e}")
            return False
    
    def get_current_model(self) -> Optional[str]:
        """Get the currently selected model"""
        return self.current_model
    
    def set_thinking_mode(self, enabled: bool):
        """
        Enable or disable thinking mode for gpt-oss models.
        
        Args:
            enabled: True to enable thinking mode, False to disable
        """
        self.thinking_mode = enabled
        logger.info(f"Thinking mode {'enabled' if enabled else 'disabled'}")
    
    def set_reasoning_level(self, level: str):
        """
        Set reasoning level for gpt-oss models.
        
        Args:
            level: 'low', 'medium', or 'high'
        """
        if level.lower() in ['low', 'medium', 'high']:
            self.reasoning_level = level.lower()
            logger.info(f"Reasoning level set to: {level}")
        else:
            logger.error("Invalid reasoning level. Use 'low', 'medium', or 'high'")
    
    def _build_system_message(self, custom_system: Optional[str] = None) -> str:
        """Build system message - simplified for GPT-OSS"""
        if custom_system:
            return custom_system
        elif self.current_model and 'gpt-oss' in self.current_model:
            # Simple system message for gpt-oss - no over-engineering
            return "You are a helpful assistant."
        else:
            return "You are a helpful assistant."
    
    def is_gpt_oss_model(self, model_name: Optional[str] = None) -> bool:
        """
        Check if the current or specified model is a gpt-oss model.
        
        Args:
            model_name: Model name to check (defaults to current model)
            
        Returns:
            True if it's a gpt-oss model
        """
        model = model_name or self.current_model
        return model is not None and 'gpt-oss' in model.lower()

    def _parse_gpt_oss_tool_call(self, cleaned_response: str) -> Optional[Dict[str, Any]]:
        """Parse cleaned response into a tool call structure"""
        try:
            # Try to parse as JSON
            if cleaned_response.strip().startswith('{'):
                data = json.loads(cleaned_response)
                
                # Check if it looks like function arguments and match with available tools
                for tool in self.selected_tools:
                    func_name = tool.get('function', {}).get('name', '')
                    params = tool.get('function', {}).get('parameters', {}).get('properties', {})
                    
                    # Check if the data matches this tool's parameters
                    if any(param_name in data for param_name in params.keys()):
                        return {
                            'id': 'call_1',
                            'type': 'function',
                            'function': {
                                'name': func_name,
                                'arguments': data
                            }
                        }
                
                # Fallback to hardcoded checks for common tools
                if 'expression' in data:  # Calculator tool
                    return {
                        'id': 'call_1',
                        'type': 'function',
                        'function': {
                            'name': 'calculate',
                            'arguments': data
                        }
                    }
                elif 'city' in data:  # Weather tool
                    return {
                        'id': 'call_1',
                        'type': 'function',
                        'function': {
                            'name': 'get_weather',
                            'arguments': data
                        }
                    }
                elif 'query' in data:  # Web search tool
                    return {
                        'id': 'call_1',
                        'type': 'function',
                        'function': {
                            'name': 'web_search',
                            'arguments': data
                        }
                    }
                    
            return None
            
        except json.JSONDecodeError:
            return None

    def _clean_tool_response(self, response_text):
        """Clean the response text by removing special tokens that interfere with JSON parsing"""
        if not response_text:
            return response_text
        
        # Remove everything after the first occurrence of special tokens
        special_tokens = ['<|call|>', '<|channel|>', '<|message|>', '<|constrain|>', '<|start|>', '<|end|>']
        
        for token in special_tokens:
            if token in response_text:
                response_text = response_text.split(token)[0]
                break
        
        # Try to extract valid JSON from the beginning
        response_text = response_text.strip()
        
        # Find the end of the first complete JSON object
        if response_text.startswith('{'):
            brace_count = 0
            json_end = -1
            in_string = False
            escape_next = False
            
            for i, char in enumerate(response_text):
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\':
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
        
            if json_end > 0:
                response_text = response_text[:json_end]
    
        return response_text

    def debug_models_raw(self) -> Dict[str, Any]:
        """
        Debug method to see the raw models response from Ollama.
        
        Returns:
            Raw response from Ollama API
        """
        try:
            response = self.client.list()
            logger.info(f"Raw response type: {type(response)}")
            logger.info(f"Raw response: {response}")
            
            if hasattr(response, 'models'):
                models = response.models
                logger.info(f"Models type: {type(models)}")
                logger.info(f"Models length: {len(models) if hasattr(models, '__len__') else 'No length'}")
                
                for i, model in enumerate(models):
                    logger.info(f"Model {i} type: {type(model)}")
                    logger.info(f"Model {i} dir: {dir(model)}")
                    logger.info(f"Model {i} dict: {model.__dict__ if hasattr(model, '__dict__') else 'No __dict__'}")
                    if i >= 2:  # Only show first 3 models for debugging
                        break
            
            return response.__dict__ if hasattr(response, '__dict__') else {'raw': str(response)}
            
        except Exception as e:
            logger.error(f"Error in debug_models_raw: {e}")
            return {'error': str(e)}

# Convenience functions for direct usage
def create_ollama_manager(host: str = "http://localhost:11434") -> OllamaManager:
    """Create and return an OllamaManager instance"""
    return OllamaManager(host=host)

def quick_chat(
    model: str, 
    message: str, 
    host: str = "http://localhost:11434"
) -> str:
    """
    Quick chat function for simple interactions.
    
    Args:
        model: Model name to use
        message: Message to send
        host: Ollama server host
        
    Returns:
        Response content as string
    """
    manager = OllamaManager(host=host)
    if manager.select_model(model):
        messages = [{"role": "user", "content": message}]
        response = manager.chat(messages)
        return response.get('message', {}).get('content', '')
    else:
        raise ValueError(f"Model {model} not found")

# Example tool definitions for gpt-oss function calling
def create_weather_tool() -> Dict[str, Any]:
    """Create a weather tool definition for function calling"""
    return {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather in a given city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "The city name"}
                },
                "required": ["city"]
            }
        }
    }

def create_calculator_tool() -> Dict[str, Any]:
    """Create a calculator tool definition for function calling"""
    return {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Perform basic mathematical calculations",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Mathematical expression to evaluate"}
                },
                "required": ["expression"]
            }
        }
    }

# Additional tool definitions
def create_web_search_tool() -> Dict[str, Any]:
    """Create a web search tool definition for function calling"""
    return {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum number of results", "default": 5}
                },
                "required": ["query"]
            }
        }
    }

def create_code_executor_tool() -> Dict[str, Any]:
    """Create a code executor tool definition for function calling"""
    return {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Execute Python code and return the result",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "language": {"type": "string", "description": "Programming language", "default": "python"}
                },
                "required": ["code"]
            }
        }
    }

def create_file_reader_tool() -> Dict[str, Any]:
    """Create a file reader tool definition for function calling"""
    return {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to the file to read"},
                    "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"}
                },
                "required": ["filepath"]
            }
        }
    }

def create_datetime_tool() -> Dict[str, Any]:
    """Create a date/time tool definition for function calling"""
    return {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Get current date and time information",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Timezone (e.g., 'UTC', 'US/Eastern')", "default": "UTC"},
                    "format": {"type": "string", "description": "Date format string", "default": "%Y-%m-%d %H:%M:%S"}
                },
                "required": []
            }
        }
    }

# Constants for available tools
DEFAULT_TOOLS = {
    "weather": "Get weather information for cities",
    "calculator": "Perform mathematical calculations",
    "web_search": "Search the web for information",
    "code_executor": "Execute Python code",
    "file_reader": "Read file contents",
    "date_time": "Get current date and time"
}

# Constants for gpt-oss models
GPT_OSS_MODELS = {
    "gpt-oss:20b": "gpt-oss:20b",
    "gpt-oss:120b": "gpt-oss:120b"
}

REASONING_LEVELS = ["low", "medium", "high"]