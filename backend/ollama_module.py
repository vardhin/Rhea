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

    def list_models(self) -> Dict[str, Any]:
        """
        List all available local models.
        
        Returns:
            Dictionary containing list of models
        """
        try:
            return self.client.list()
            
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            raise

    def select_model(self, model_name: str) -> bool:
        """
        Select a model to use for subsequent operations.
        
        Args:
            model_name: Name of the model to select
            
        Returns:
            True if model exists and was selected
        """
        try:
            # Check if model exists
            models = self.list_models()
            available_models = [m['name'] for m in models.get('models', [])]
            
            if model_name in available_models:
                self.current_model = model_name
                logger.info(f"Selected model: {model_name}")
                return True
            else:
                logger.error(f"Model {model_name} not found. Available: {available_models}")
                return False
                
        except Exception as e:
            logger.error(f"Error selecting model {model_name}: {e}")
            return False

    def set_thinking_mode(self, enabled: bool, reasoning_level: str = "medium"):
        """
        Enable or disable thinking mode for gpt-oss models.
        
        Args:
            enabled: Whether to enable thinking mode
            reasoning_level: Level of reasoning ("low", "medium", "high")
        """
        if reasoning_level not in REASONING_LEVELS:
            logger.warning(f"Invalid reasoning level: {reasoning_level}. Using 'medium'")
            reasoning_level = "medium"
            
        self.thinking_mode = enabled
        self.reasoning_level = reasoning_level
        logger.info(f"Thinking mode: {enabled}, Level: {reasoning_level}")

    def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get detailed information about a model.
        
        Args:
            model_name: Model name (defaults to current model)
            
        Returns:
            Model information
        """
        use_model = model_name or self.current_model
        if not use_model:
            raise ValueError("No model specified")
            
        return self.show_model(use_model, verbose=True)

    def set_model_parameters(
        self,
        model_name: Optional[str] = None,
        num_ctx: Optional[int] = None,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        seed: Optional[int] = None,
        num_predict: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Set model parameters by creating a custom model configuration.
        
        Args:
            model_name: Base model name (defaults to current model)
            num_ctx: Context window size (e.g., 4096, 8192, 32768)
            temperature: Sampling temperature (0.0 to 2.0)
            top_k: Top-k sampling parameter
            top_p: Top-p sampling parameter
            repeat_penalty: Repetition penalty
            seed: Random seed for reproducible outputs
            num_predict: Maximum tokens to predict
            **kwargs: Additional model parameters
            
        Returns:
            Dictionary of applied parameters
        """
        use_model = model_name or self.current_model
        if not use_model:
            raise ValueError("No model specified")
        
        # Build parameters dictionary
        parameters = {}
        
        if num_ctx is not None:
            parameters['num_ctx'] = num_ctx
        if temperature is not None:
            parameters['temperature'] = temperature
        if top_k is not None:
            parameters['top_k'] = top_k
        if top_p is not None:
            parameters['top_p'] = top_p
        if repeat_penalty is not None:
            parameters['repeat_penalty'] = repeat_penalty
        if seed is not None:
            parameters['seed'] = seed
        if num_predict is not None:
            parameters['num_predict'] = num_predict
            
        # Add any additional parameters
        parameters.update(kwargs)
        
        logger.info(f"Set parameters for {use_model}: {parameters}")
        return parameters

    def chat_with_options(
        self,
        messages: List[Dict[str, str]],
        num_ctx: Optional[int] = None,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        seed: Optional[int] = None,
        num_predict: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Chat with specific model parameters.
        
        Args:
            messages: Chat messages
            num_ctx: Context window size
            temperature: Sampling temperature
            top_k: Top-k sampling
            top_p: Top-p sampling  
            repeat_penalty: Repetition penalty
            seed: Random seed
            num_predict: Max tokens to predict
            stream: Stream response
            **kwargs: Additional options
            
        Returns:
            Chat response
        """
        if not self.current_model:
            raise ValueError("No model selected")
        
        # Build options dictionary
        options = {}
        
        if num_ctx is not None:
            options['num_ctx'] = num_ctx
        if temperature is not None:
            options['temperature'] = temperature
        if top_k is not None:
            options['top_k'] = top_k
        if top_p is not None:
            options['top_p'] = top_p
        if repeat_penalty is not None:
            options['repeat_penalty'] = repeat_penalty
        if seed is not None:
            options['seed'] = seed
        if num_predict is not None:
            options['num_predict'] = num_predict
            
        # Add additional options
        options.update(kwargs)
        
        try:
            chat_kwargs = {
                'model': self.current_model,
                'messages': messages,
                'stream': stream,
                'options': options
            }
            
            # Add thinking mode for gpt-oss models
            if self.current_model and 'gpt-oss' in self.current_model and self.thinking_mode:
                chat_kwargs['think'] = self.reasoning_level
            
            return self.client.chat(**chat_kwargs)
            
        except Exception as e:
            logger.error(f"Error in chat with options: {e}")
            raise

    def generate_with_options(
        self,
        prompt: str,
        num_ctx: Optional[int] = None,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        seed: Optional[int] = None,
        num_predict: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Generate with specific model parameters.
        
        Args:
            prompt: Input prompt
            num_ctx: Context window size
            temperature: Sampling temperature
            top_k: Top-k sampling
            top_p: Top-p sampling
            repeat_penalty: Repetition penalty
            seed: Random seed
            num_predict: Max tokens to predict
            stream: Stream response
            **kwargs: Additional options
            
        Returns:
            Generation response
        """
        if not self.current_model:
            raise ValueError("No model selected")
        
        # Build options dictionary
        options = {}
        
        if num_ctx is not None:
            options['num_ctx'] = num_ctx
        if temperature is not None:
            options['temperature'] = temperature
        if top_k is not None:
            options['top_k'] = top_k
        if top_p is not None:
            options['top_p'] = top_p
        if repeat_penalty is not None:
            options['repeat_penalty'] = repeat_penalty
        if seed is not None:
            options['seed'] = seed
        if num_predict is not None:
            options['num_predict'] = num_predict
            
        # Add additional options
        options.update(kwargs)
        
        return self.generate(
            prompt=prompt,
            options=options,
            stream=stream,
            **kwargs
        )

    def create_custom_model(
        self,
        model_name: str,
        base_model: str,
        system_prompt: Optional[str] = None,
        template: Optional[str] = None,
        num_ctx: Optional[int] = None,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        **kwargs
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Create a custom model with specific parameters and system prompt.
        
        Args:
            model_name: Name for the new model
            base_model: Base model to extend from
            system_prompt: Custom system prompt
            template: Custom template
            num_ctx: Context window size
            temperature: Default temperature
            top_k: Default top-k
            top_p: Default top-p
            repeat_penalty: Default repeat penalty
            **kwargs: Additional parameters
            
        Returns:
            Model creation response
        """
        # Build parameters dictionary
        parameters = {}
        
        if num_ctx is not None:
            parameters['num_ctx'] = num_ctx
        if temperature is not None:
            parameters['temperature'] = temperature
        if top_k is not None:
            parameters['top_k'] = top_k
        if top_p is not None:
            parameters['top_p'] = top_p
        if repeat_penalty is not None:
            parameters['repeat_penalty'] = repeat_penalty
            
        # Add additional parameters
        parameters.update(kwargs)
        
        return self.create_model(
            model=model_name,
            from_model=base_model,
            system=system_prompt,
            template=template,
            parameters=parameters
        )

    def get_context_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get context window information for a model.
        
        Args:
            model_name: Model name (defaults to current model)
            
        Returns:
            Context information including max context length
        """
        use_model = model_name or self.current_model
        if not use_model:
            raise ValueError("No model specified")
        
        try:
            model_info = self.show_model(use_model, verbose=True)
            context_info = {}
            
            # Extract context information from model info
            if 'model_info' in model_info:
                model_details = model_info['model_info']
                
                # Look for context length in various fields
                for key in ['llama.context_length', 'context_length', 'n_ctx']:
                    if key in model_details:
                        context_info['max_context_length'] = model_details[key]
                        break
                        
                # Add other relevant info
                context_info.update({
                    'model_name': use_model,
                    'parameter_size': model_info.get('details', {}).get('parameter_size', 'Unknown'),
                    'family': model_info.get('details', {}).get('family', 'Unknown')
                })
                
            return context_info
            
        except Exception as e:
            logger.error(f"Error getting context info for {use_model}: {e}")
            return {'error': str(e)}

    def _build_system_message(self, custom_message: Optional[str] = None) -> str:
        """
        Build system message for gpt-oss models.
        
        Args:
            custom_message: Custom system message
            
        Returns:
            System message string
        """
        if custom_message:
            return custom_message
            
        if self.current_model and 'gpt-oss' in self.current_model:
            return "You are a helpful AI assistant with reasoning capabilities. Think step by step when solving problems."
        
        return "You are a helpful AI assistant."

    def _clean_tool_response(self, response: str) -> str:
        """Clean tool response for parsing"""
        # Remove common formatting issues
        response = response.strip()
        response = response.replace('\\n', '\n').replace('\\"', '"')
        return response

    def _parse_gpt_oss_tool_call(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse GPT-OSS tool call format"""
        try:
            # Try to parse as JSON
            parsed = json.loads(response)
            
            # Check if it's a tool call format
            if isinstance(parsed, dict) and 'function' in parsed:
                return parsed
                
            return None
        except json.JSONDecodeError:
            return None

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

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        suffix: Optional[str] = None,
        images: Optional[List[str]] = None,
        format: Optional[Union[str, Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        system: Optional[str] = None,
        template: Optional[str] = None,
        stream: bool = False,
        raw: bool = False,
        context: Optional[List[int]] = None,
        keep_alive: Optional[Union[str, int]] = None
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Generate a completion for a given prompt.
        
        Args:
            prompt: The prompt to generate a response for
            model: Model name to use (defaults to current model)
            suffix: Text after the model response
            images: List of base64-encoded images for multimodal models
            format: Format to return response in ("json" or JSON schema)
            options: Additional model parameters
            system: System message (overrides Modelfile)
            template: Prompt template (overrides Modelfile)
            stream: Stream the response
            raw: Skip formatting/templating
            context: Context from previous request
            keep_alive: How long to keep model loaded
            
        Returns:
            Generation response or stream generator
        """
        use_model = model or self.current_model
        if not use_model:
            raise ValueError("No model specified. Use model parameter or select_model() first.")
        
        try:
            kwargs = {
                'model': use_model,
                'prompt': prompt,
                'stream': stream
            }
            
            if suffix is not None:
                kwargs['suffix'] = suffix
            if images is not None:
                kwargs['images'] = images
            if format is not None:
                kwargs['format'] = format
            if options is not None:
                kwargs['options'] = options
            if system is not None:
                kwargs['system'] = system
            if template is not None:
                kwargs['template'] = template
            if raw:
                kwargs['raw'] = raw
            if context is not None:
                kwargs['context'] = context
            if keep_alive is not None:
                kwargs['keep_alive'] = keep_alive
            
            # Add thinking mode for gpt-oss models
            if use_model and 'gpt-oss' in use_model and self.thinking_mode:
                kwargs['think'] = self.reasoning_level
            
            return self.client.generate(**kwargs)
            
        except Exception as e:
            logger.error(f"Error in generate: {e}")
            raise

    async def generate_async(
        self,
        prompt: str,
        model: Optional[str] = None,
        suffix: Optional[str] = None,
        images: Optional[List[str]] = None,
        format: Optional[Union[str, Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        system: Optional[str] = None,
        template: Optional[str] = None,
        stream: bool = False,
        raw: bool = False,
        context: Optional[List[int]] = None,
        keep_alive: Optional[Union[str, int]] = None
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """Async version of generate method"""
        use_model = model or self.current_model
        if not use_model:
            raise ValueError("No model specified. Use model parameter or select_model() first.")
        
        try:
            kwargs = {
                'model': use_model,
                'prompt': prompt,
                'stream': stream
            }
            
            if suffix is not None:
                kwargs['suffix'] = suffix
            if images is not None:
                kwargs['images'] = images
            if format is not None:
                kwargs['format'] = format
            if options is not None:
                kwargs['options'] = options
            if system is not None:
                kwargs['system'] = system
            if template is not None:
                kwargs['template'] = template
            if raw:
                kwargs['raw'] = raw
            if context is not None:
                kwargs['context'] = context
            if keep_alive is not None:
                kwargs['keep_alive'] = keep_alive
            
            # Add thinking mode for gpt-oss models
            if use_model and 'gpt-oss' in use_model and self.thinking_mode:
                kwargs['think'] = self.reasoning_level
            
            return await self.async_client.generate(**kwargs)
            
        except Exception as e:
            logger.error(f"Error in async generate: {e}")
            raise

    def create_model(
        self,
        model: str,
        from_model: Optional[str] = None,
        files: Optional[Dict[str, str]] = None,
        adapters: Optional[Dict[str, str]] = None,
        template: Optional[str] = None,
        license: Optional[Union[str, List[str]]] = None,
        system: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        stream: bool = True,
        quantize: Optional[str] = None
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Create a model from another model, safetensors directory, or GGUF file.
        
        Args:
            model: Name of the model to create
            from_model: Name of existing model to create from
            files: Dictionary of file names to SHA256 digests
            adapters: Dictionary of LORA adapter files
            template: Prompt template for the model
            license: License(s) for the model
            system: System prompt for the model
            parameters: Model parameters
            messages: Message objects for conversation
            stream: Stream the response
            quantize: Quantization type (e.g., "q4_K_M", "q8_0")
            
        Returns:
            Creation response or stream generator
        """
        try:
            kwargs = {
                'model': model,
                'stream': stream
            }
            
            if from_model is not None:
                kwargs['from'] = from_model
            if files is not None:
                kwargs['files'] = files
            if adapters is not None:
                kwargs['adapters'] = adapters
            if template is not None:
                kwargs['template'] = template
            if license is not None:
                kwargs['license'] = license
            if system is not None:
                kwargs['system'] = system
            if parameters is not None:
                kwargs['parameters'] = parameters
            if messages is not None:
                kwargs['messages'] = messages
            if quantize is not None:
                kwargs['quantize'] = quantize
            
            return self.client.create(**kwargs)
            
        except Exception as e:
            logger.error(f"Error creating model: {e}")
            raise

    def show_model(self, model: str, verbose: bool = False) -> Dict[str, Any]:
        """
        Show information about a model including details, modelfile, template, etc.
        
        Args:
            model: Name of the model to show
            verbose: Return full data for verbose response fields
            
        Returns:
            Model information dictionary
        """
        try:
            kwargs = {'model': model}
            if verbose:
                kwargs['verbose'] = verbose
                
            return self.client.show(**kwargs)
            
        except Exception as e:
            logger.error(f"Error showing model {model}: {e}")
            raise

    def copy_model(self, source: str, destination: str) -> bool:
        """
        Copy a model to create a new model with another name.
        
        Args:
            source: Name of the source model
            destination: Name of the destination model
            
        Returns:
            True if successful
        """
        try:
            self.client.copy(source=source, destination=destination)
            logger.info(f"Copied model {source} to {destination}")
            return True
            
        except Exception as e:
            logger.error(f"Error copying model {source} to {destination}: {e}")
            return False

    def delete_model(self, model: str) -> bool:
        """
        Delete a model and its data.
        
        Args:
            model: Name of the model to delete
            
        Returns:
            True if successful
        """
        try:
            self.client.delete(model=model)
            logger.info(f"Deleted model {model}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting model {model}: {e}")
            return False

    def pull_model(
        self,
        model: str,
        insecure: bool = False,
        stream: bool = True
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Download a model from the ollama library.
        
        Args:
            model: Name of the model to pull
            insecure: Allow insecure connections
            stream: Stream the response
            
        Returns:
            Pull response or stream generator
        """
        try:
            kwargs = {
                'model': model,
                'stream': stream
            }
            
            if insecure:
                kwargs['insecure'] = insecure
            
            return self.client.pull(**kwargs)
            
        except Exception as e:
            logger.error(f"Error pulling model {model}: {e}")
            raise

    def push_model(
        self,
        model: str,
        insecure: bool = False,
        stream: bool = True
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Upload a model to a model library.
        
        Args:
            model: Name of the model to push (format: <namespace>/<model>:<tag>)
            insecure: Allow insecure connections
            stream: Stream the response
            
        Returns:
            Push response or stream generator
        """
        try:
            kwargs = {
                'model': model,
                'stream': stream
            }
            
            if insecure:
                kwargs['insecure'] = insecure
            
            return self.client.push(**kwargs)
            
        except Exception as e:
            logger.error(f"Error pushing model {model}: {e}")
            raise

    def generate_embeddings(
        self,
        input_text: Union[str, List[str]],
        model: Optional[str] = None,
        truncate: bool = True,
        options: Optional[Dict[str, Any]] = None,
        keep_alive: Optional[Union[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Generate embeddings from a model.
        
        Args:
            input_text: Text or list of text to generate embeddings for
            model: Model name to use (defaults to current model)
            truncate: Truncate input to fit context length
            options: Additional model parameters
            keep_alive: How long to keep model loaded
            
        Returns:
            Embeddings response
        """
        use_model = model or self.current_model
        if not use_model:
            raise ValueError("No model specified. Use model parameter or select_model() first.")
        
        try:
            kwargs = {
                'model': use_model,
                'input': input_text,
                'truncate': truncate
            }
            
            if options is not None:
                kwargs['options'] = options
            if keep_alive is not None:
                kwargs['keep_alive'] = keep_alive
            
            return self.client.embed(**kwargs)
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def list_running_models(self) -> Dict[str, Any]:
        """
        List models that are currently loaded into memory.
        
        Returns:
            Dictionary containing list of running models
        """
        try:
            return self.client.ps()
            
        except Exception as e:
            logger.error(f"Error listing running models: {e}")
            raise

    def get_version(self) -> Dict[str, str]:
        """
        Get Ollama version information.
        
        Returns:
            Version information dictionary
        """
        try:
            # Direct HTTP request since ollama client might not have version method
            import requests
            response = requests.get(f"{self.host}/api/version")
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting version: {e}")
            raise

    def check_blob_exists(self, digest: str) -> bool:
        """
        Check if a blob exists on the server.
        
        Args:
            digest: SHA256 digest of the blob
            
        Returns:
            True if blob exists
        """
        try:
            import requests
            response = requests.head(f"{self.host}/api/blobs/{digest}")
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error checking blob {digest}: {e}")
            return False

    def push_blob(self, file_path: str, digest: str) -> bool:
        """
        Push a file to create a blob on the server.
        
        Args:
            file_path: Path to the file to upload
            digest: Expected SHA256 digest of the file
            
        Returns:
            True if successful
        """
        try:
            import requests
            with open(file_path, 'rb') as f:
                response = requests.post(
                    f"{self.host}/api/blobs/{digest}",
                    data=f,
                    headers={'Content-Type': 'application/octet-stream'}
                )
            response.raise_for_status()
            logger.info(f"Successfully pushed blob {digest}")
            return True
            
        except Exception as e:
            logger.error(f"Error pushing blob {digest}: {e}")
            return False

    def load_model(self, model: str) -> bool:
        """
        Load a model into memory.
        
        Args:
            model: Name of the model to load
            
        Returns:
            True if successful
        """
        try:
            # Load model by sending empty prompt to generate endpoint
            self.client.generate(model=model, prompt="")
            logger.info(f"Loaded model {model}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model {model}: {e}")
            return False

    def unload_model(self, model: str) -> bool:
        """
        Unload a model from memory.
        
        Args:
            model: Name of the model to unload
            
        Returns:
            True if successful
        """
        try:
            # Unload model by setting keep_alive to 0
            self.client.generate(model=model, prompt="", keep_alive=0)
            logger.info(f"Unloaded model {model}")
            return True
            
        except Exception as e:
            logger.error(f"Error unloading model {model}: {e}")
            return False

    # Legacy embedding method for compatibility
    def embeddings(
        self,
        prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        keep_alive: Optional[Union[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Generate embeddings (legacy method - use generate_embeddings instead).
        
        Args:
            prompt: Text to generate embeddings for
            model: Model name to use
            options: Additional model parameters
            keep_alive: How long to keep model loaded
            
        Returns:
            Embeddings response
        """
        try:
            import requests
            use_model = model or self.current_model
            if not use_model:
                raise ValueError("No model specified")
            
            payload = {
                'model': use_model,
                'prompt': prompt
            }
            
            if options is not None:
                payload['options'] = options
            if keep_alive is not None:
                payload['keep_alive'] = keep_alive
            
            response = requests.post(f"{self.host}/api/embeddings", json=payload)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error generating embeddings (legacy): {e}")
            raise

    def get_server_info(self) -> Dict[str, Any]:
        """
        Get comprehensive server information including version and running models.
        
        Returns:
            Server information dictionary
        """
        try:
            info = {}
            info['version'] = self.get_version()
            info['running_models'] = self.list_running_models()
            info['available_models'] = self.list_models()
            info['server_host'] = self.host
            return info
            
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
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

# Additional constants for model parameters
MODEL_PARAMETERS = {
    'num_ctx': 'Context window size (tokens)',
    'temperature': 'Sampling temperature (0.0-2.0)',
    'top_k': 'Top-k sampling parameter',
    'top_p': 'Top-p sampling parameter (0.0-1.0)',
    'repeat_penalty': 'Repetition penalty (1.0+)',
    'seed': 'Random seed for reproducible outputs',
    'num_predict': 'Maximum tokens to predict',
    'num_keep': 'Number of tokens to keep from prompt',
    'stop': 'Stop sequences',
    'min_p': 'Minimum probability threshold',
    'typical_p': 'Typical probability mass',
    'repeat_last_n': 'Tokens to consider for repetition penalty',
    'presence_penalty': 'Presence penalty',
    'frequency_penalty': 'Frequency penalty',
    'penalize_newline': 'Penalize newlines in output',
    'numa': 'Use NUMA optimization',
    'num_batch': 'Batch size for processing',
    'num_gpu': 'Number of GPUs to use',
    'main_gpu': 'Main GPU to use',
    'use_mmap': 'Use memory mapping',
    'num_thread': 'Number of threads to use'
}

# Common context window sizes
CONTEXT_SIZES = {
    2048: "2K tokens",
    4096: "4K tokens", 
    8192: "8K tokens",
    16384: "16K tokens",
    32768: "32K tokens",
    65536: "64K tokens",
    131072: "128K tokens"
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

# Additional constants for quantization types
QUANTIZATION_TYPES = {
    "q4_K_M": "Q4_K_M (Recommended)",
    "q4_K_S": "Q4_K_S",
    "q8_0": "Q8_0 (Recommended)",
    "q4_0": "Q4_0",
    "q4_1": "Q4_1",
    "q5_0": "Q5_0",
    "q5_1": "Q5_1",
    "q2_K": "Q2_K",
    "q3_K_S": "Q3_K_S",
    "q3_K_M": "Q3_K_M",
    "q3_K_L": "Q3_K_L",
    "q4_K": "Q4_K",
    "q5_K_S": "Q5_K_S",
    "q5_K_M": "Q5_K_M",
    "q6_K": "Q6_K"
}

# Format options
FORMAT_OPTIONS = {
    "json": "JSON format",
    "structured": "Structured output with schema"
}