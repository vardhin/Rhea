from google import genai
import json
import os

def fetch_gemini_models(api_key):
    """
    Fetches the list of available models from Google Gemini.

    Args:
        api_key (str): The Gemini API key (required).

    Returns:
        list: A list of model objects with detailed information.
    
    Raises:
        ValueError: If api_key is None or empty.
    """
    if not api_key:
        raise ValueError("API key is required. Please provide a valid Gemini API key.")
    
    try:
        client = genai.Client(api_key=api_key)
        models = client.models.list()
        
        # Convert to list format similar to ollama_module
        model_list = []
        for model in models:
            model_list.append({
                "name": model.name,
                "display_name": getattr(model, 'display_name', model.name),
                "description": getattr(model, 'description', ''),
            })
        return model_list
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

def get_model_info(model_name, api_key):
    """
    Get detailed information about a specific Gemini model.
    
    Args:
        model_name (str): The name of the model to get info for.
        api_key (str): The Gemini API key (required).
        
    Returns:
        dict: Model information including details, parameters, etc.
    
    Raises:
        ValueError: If api_key is None or empty.
    """
    if not api_key:
        raise ValueError("API key is required. Please provide a valid Gemini API key.")
    
    try:
        client = genai.Client(api_key=api_key)
        model = client.models.get(model=model_name)
        
        return {
            "name": model.name,
            "display_name": getattr(model, 'display_name', model.name),
            "description": getattr(model, 'description', ''),
            "input_token_limit": getattr(model, 'input_token_limit', 0),
            "output_token_limit": getattr(model, 'output_token_limit', 0),
            "supported_generation_methods": getattr(model, 'supported_generation_methods', []),
        }
    except Exception as e:
        print(f"Error fetching model info for {model_name}: {e}")
        return {}

def get_default_parameters_for_model(model_name, api_key):
    """
    Get the default parameters for a specific Gemini model.
    
    Args:
        model_name (str): The name of the model.
        api_key (str): The Gemini API key (required).
        
    Returns:
        dict: Default parameters for the model.
    
    Raises:
        ValueError: If api_key is None or empty.
    """
    if not api_key:
        raise ValueError("API key is required. Please provide a valid Gemini API key.")
    
    try:
        model_info = get_model_info(model_name, api_key)
        
        # Gemini default parameters
        default_params = {
            "temperature": 1.0,
            "top_k": 40,
            "top_p": 0.95,
            "max_output_tokens": model_info.get("output_token_limit", 8192),
            "candidate_count": 1,
        }
        
        return default_params
    except Exception as e:
        print(f"Error getting default parameters for {model_name}: {e}")
        return {
            "temperature": 1.0,
            "top_k": 40,
            "top_p": 0.95,
            "max_output_tokens": 8192,
            "candidate_count": 1,
        }

def get_model_capabilities(model_name, api_key):
    """
    Get capabilities of a specific Gemini model.
    
    Args:
        model_name (str): The name of the model.
        api_key (str): The Gemini API key (required).
        
    Returns:
        dict: Model capabilities.
    
    Raises:
        ValueError: If api_key is None or empty.
    """
    if not api_key:
        raise ValueError("API key is required. Please provide a valid Gemini API key.")
    
    try:
        model_info = get_model_info(model_name, api_key)
        
        capabilities = {
            "function_calling": "generateContent" in model_info.get("supported_generation_methods", []),
            "system_messages": True,
            "streaming": True,
            "context_length": model_info.get("input_token_limit", 0),
            "max_output_tokens": model_info.get("output_token_limit", 0),
            "thinking_mode": "gemini-2" in model_name.lower(),  # Gemini 2.0+ supports thinking
        }
        
        return capabilities
    except Exception as e:
        print(f"Error getting capabilities for {model_name}: {e}")
        return {
            "function_calling": False,
            "system_messages": True,
            "streaming": True,
            "context_length": 0,
            "max_output_tokens": 0,
            "thinking_mode": False,
        }

def get_gemini_api_info(api_key):
    """
    Get information about the Gemini API connection.
    
    Args:
        api_key (str): The Gemini API key (required).
        
    Returns:
        dict: API information including status, etc.
    
    Raises:
        ValueError: If api_key is None or empty.
    """
    if not api_key:
        raise ValueError("API key is required. Please provide a valid Gemini API key.")
    
    try:
        client = genai.Client(api_key=api_key)
        # Test connectivity by listing models
        models = client.models.list()
        
        return {
            "connected": True,
            "status": "connected",
            "models_available": len(list(models)),
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "status": "error"
        }

# Global state for current configuration
_current_config = {
    "selected_model": None,
    "thinking_mode": {
        "enabled": False,
        "level": 1
    },
    "parameters": None,
    "api_key": None
}

def set_api_key(api_key):
    """
    Set the Gemini API key.
    
    Args:
        api_key (str): The Gemini API key (required).
    
    Raises:
        ValueError: If api_key is None or empty.
    """
    if not api_key:
        raise ValueError("API key is required. Please provide a valid Gemini API key.")
    
    global _current_config
    _current_config["api_key"] = api_key

def get_current_parameters(model_name=None, api_key=None):
    """
    Get current model parameters, fetching defaults from Gemini if needed.
    
    Args:
        model_name (str): Optional model name to get specific parameters for.
        api_key (str): The Gemini API key (uses stored key if not provided).
    
    Returns:
        dict: Current parameters configuration.
    
    Raises:
        ValueError: If api_key is None or empty and no key is stored.
    """
    global _current_config
    
    # Use provided api_key or fall back to stored key
    active_api_key = api_key or _current_config["api_key"]
    if not active_api_key:
        raise ValueError("API key is required. Please provide a valid Gemini API key or set it using set_api_key().")
    
    target_model = model_name or _current_config["selected_model"]
    
    if _current_config["parameters"] is None or _current_config["selected_model"] != target_model:
        if target_model:
            _current_config["parameters"] = get_default_parameters_for_model(
                target_model, active_api_key
            )
            _current_config["selected_model"] = target_model
        else:
            _current_config["parameters"] = {
                "temperature": 1.0,
                "top_k": 40,
                "top_p": 0.95,
                "max_output_tokens": 8192,
                "candidate_count": 1,
            }
    
    return _current_config["parameters"].copy()

def set_parameters(parameters, model_name=None, api_key=None):
    """
    Set model parameters.
    
    Args:
        parameters (dict): Dictionary of parameters to update.
        model_name (str): Optional model name to set parameters for.
        api_key (str): The Gemini API key (uses stored key if not provided).
        
    Returns:
        dict: Updated parameters.
    """
    global _current_config
    
    current_params = get_current_parameters(model_name, api_key)
    current_params.update(parameters)
    _current_config["parameters"] = current_params
    
    return _current_config["parameters"].copy()

def get_thinking_mode():
    """
    Get current thinking mode configuration.
    
    Returns:
        dict: Current thinking mode settings.
    """
    return _current_config["thinking_mode"].copy()

def set_thinking_mode(enabled, level=1):
    """
    Toggle thinking mode and set reasoning level.
    
    Args:
        enabled (bool): Whether to enable thinking mode.
        level (int): Reasoning level (1-3, where 3 is most detailed).
        
    Returns:
        dict: Updated thinking mode configuration.
    """
    global _current_config
    _current_config["thinking_mode"]["enabled"] = enabled
    _current_config["thinking_mode"]["level"] = max(1, min(3, level))
    
    return _current_config["thinking_mode"].copy()

def send_message_to_gemini_model(model, message, stream=False, api_key=None, system_message=""):
    """
    Sends a message to a specified Gemini model and returns the response.

    Args:
        model (str): The name of the model to use.
        message (str): The message to send.
        stream (bool): Whether to stream the response or get the full output.
        api_key (str): The Gemini API key (uses stored key if not provided).
        system_message (str): System message to include.

    Returns:
        str or generator: The full response as a string, or a generator yielding streamed chunks.
    
    Raises:
        ValueError: If api_key is None or empty and no key is stored.
    """
    # Use provided api_key or fall back to stored key
    active_api_key = api_key or _current_config["api_key"]
    if not active_api_key:
        raise ValueError("API key is required. Please provide a valid Gemini API key or set it using set_api_key().")
    
    try:
        client = genai.Client(api_key=active_api_key)
        
        # Get current parameters for this model
        parameters = get_current_parameters(model, active_api_key)
        
        # Build generation config
        generation_config = {
            "temperature": parameters.get("temperature", 1.0),
            "top_k": parameters.get("top_k", 40),
            "top_p": parameters.get("top_p", 0.95),
            "max_output_tokens": parameters.get("max_output_tokens", 8192),
            "candidate_count": parameters.get("candidate_count", 1),
        }
        
        # Handle thinking mode
        thinking_config = get_thinking_mode()
        content = message
        
        if thinking_config["enabled"]:
            level_map = {1: "low", 2: "medium", 3: "high"}
            thinking_level = level_map.get(thinking_config["level"], "medium")
            
            thinking_system = "You may use <think></think> tags to show your reasoning process when helpful."
            full_system = f"{system_message} {thinking_system}" if system_message else thinking_system
            
            # Prepend system message to content for Gemini
            content = f"{full_system}\n\n{message}"
            print(f"🧠 Thinking mode enabled (level: {thinking_level})")
        else:
            no_thinking_system = "Respond directly without showing your internal reasoning or using <think></think> tags. Provide clear, concise answers."
            full_system = f"{system_message} {no_thinking_system}" if system_message else no_thinking_system
            
            content = f"{full_system}\n\n{message}"
            print("🚫 Thinking mode disabled - direct response mode")
        
        if stream:
            def stream_generator():
                response = client.models.generate_content_stream(
                    model=model,
                    contents=content,
                    config=generation_config
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
            return stream_generator()
        else:
            response = client.models.generate_content(
                model=model,
                contents=content,
                config=generation_config
            )
            
            response_text = response.text
            
            # Post-process response to remove thinking tags if thinking is disabled
            if not thinking_config["enabled"]:
                response_text = _remove_thinking_tags(response_text)
            
            return response_text
            
    except Exception as e:
        print(f"Error sending message to model {model}: {e}")
        return f"Error: {str(e)}"

def _remove_thinking_tags(text):
    """
    Remove <think></think> tags and their content from the response.
    
    Args:
        text (str): The response text that may contain thinking tags.
        
    Returns:
        str: The cleaned response text.
    """
    import re
    
    # Remove <think>...</think> blocks (including multiline)
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # Clean up extra whitespace and newlines
    cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

def get_full_config(api_key=None):
    """
    Get complete current configuration.
    
    Args:
        api_key (str): The Gemini API key (uses stored key if not provided).
    
    Returns:
        dict: Full configuration including API status, parameters, etc.
    """
    global _current_config
    
    # Use provided api_key or fall back to stored key
    active_api_key = api_key or _current_config["api_key"]
    if not active_api_key:
        return {
            "error": "API key is required. Please provide a valid Gemini API key or set it using set_api_key().",
        }
    
    try:
        api_info = get_gemini_api_info(active_api_key)
        
        return {
            "api": api_info,
            "parameters": _current_config["parameters"],
            "thinking_mode": _current_config["thinking_mode"],
            "selected_model": _current_config["selected_model"],
        }
    except Exception as e:
        return {
            "error": f"Error getting configuration: {str(e)}",
        }

# Example usage:
if __name__ == "__main__":
    # Load API key from environment variable (using dotenv in actual usage)
    # from dotenv import load_dotenv
    # load_dotenv()
    # api_key = os.getenv("GEMINI_API_KEY")
    
    # For testing, you would pass the API key explicitly
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        exit(1)
    
    # Set the API key globally
    set_api_key(api_key)
    
    # Test API connection
    api_info = get_gemini_api_info(api_key)
    print(f"API info: {api_info}")
    
    # Test fetching models
    models = fetch_gemini_models(api_key)
    print(f"Available models: {[m['name'] for m in models]}")
    
    if models:
        # Test model info
        first_model = models[0]['name']
        model_info = get_model_info(first_model, api_key)
        print(f"Model info for {first_model}: {model_info}")
        
        # Test capabilities
        capabilities = get_model_capabilities(first_model, api_key)
        print(f"Capabilities for {first_model}: {capabilities}")
        
        # Test default parameters
        params = get_default_parameters_for_model(first_model, api_key)
        print(f"Default parameters: {params}")
    
    # Test thinking mode
    set_thinking_mode(True, 2)
    thinking = get_thinking_mode()
    print(f"Thinking mode: {thinking}")
    
    # Test full config
    config = get_full_config(api_key)
    print(f"Full config keys: {list(config.keys())}")