import requests
import json

def fetch_local_ollama_models(base_url="http://localhost:11434"):
    """
    Fetches the list of available models from the local Ollama server.

    Args:
        base_url (str): The base URL of the Ollama server.

    Returns:
        list: A list of model objects with detailed information.
    """
    try:
        response = requests.get(f"{base_url}/api/tags")
        response.raise_for_status()
        data = response.json()
        return data.get("models", [])
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

def get_model_info(model_name, base_url="http://localhost:11434"):
    """
    Get detailed information about a specific model.
    
    Args:
        model_name (str): The name of the model to get info for.
        base_url (str): The base URL of the Ollama server.
        
    Returns:
        dict: Model information including details, parameters, etc.
    """
    try:
        response = requests.post(f"{base_url}/api/show", json={"name": model_name})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching model info for {model_name}: {e}")
        return {}

def get_default_parameters_for_model(model_name, base_url="http://localhost:11434"):
    """
    Get the default parameters for a specific model from Ollama, 
    extracting actual values from model info when available.
    
    Args:
        model_name (str): The name of the model.
        base_url (str): The base URL of the Ollama server.
        
    Returns:
        dict: Default parameters for the model.
    """
    try:
        model_info = get_model_info(model_name, base_url)
        
        # Start with sensible defaults
        default_params = {
            "temperature": 0.8,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "num_ctx": 2048,
            "num_predict": -1,
            "tfs_z": 1.0,
            "typical_p": 1.0,
            "repeat_last_n": 64,
            "mirostat": 0,
            "mirostat_tau": 5.0,
            "mirostat_eta": 0.1,
        }
        
        # Extract actual context length from model info
        if "model_info" in model_info:
            model_details = model_info["model_info"]
            
            # Get context length from model architecture
            if "gpt-oss.context_length" in model_details:
                default_params["num_ctx"] = model_details["gpt-oss.context_length"]
            elif "llama.context_length" in model_details:
                default_params["num_ctx"] = model_details["llama.context_length"]
                
        # Extract parameters from the parameters field if available
        if "parameters" in model_info and model_info["parameters"]:
            param_string = model_info["parameters"]
            # Parse parameter string (e.g., "temperature 1")
            for line in param_string.split('\n'):
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        param_name = parts[0].lower()
                        try:
                            param_value = float(parts[1])
                            if param_name in default_params:
                                default_params[param_name] = param_value
                        except ValueError:
                            pass
            
        return default_params
    except Exception as e:
        print(f"Error getting default parameters for {model_name}: {e}")
        return {
            "temperature": 0.8,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "num_ctx": 2048,
        }

def get_model_capabilities(model_name, base_url="http://localhost:11434"):
    """
    Get capabilities of a specific model (like function calling support).
    
    Args:
        model_name (str): The name of the model.
        base_url (str): The base URL of the Ollama server.
        
    Returns:
        dict: Model capabilities.
    """
    try:
        model_info = get_model_info(model_name, base_url)
        
        # Default capabilities
        capabilities = {
            "function_calling": False,
            "system_messages": True,
            "streaming": True,
            "context_length": 2048,
            "parameter_size": "unknown",
            "thinking_mode": False
        }
        
        # Extract from model details
        if "details" in model_info:
            details = model_info["details"]
            if "parameter_size" in details:
                capabilities["parameter_size"] = details["parameter_size"]
            if "family" in details:
                family = details["family"].lower()
                # GPT-OSS models support function calling
                if "gpt-oss" in family:
                    capabilities["function_calling"] = True
                    capabilities["thinking_mode"] = True
        
        # Extract context length from model_info
        if "model_info" in model_info:
            model_details = model_info["model_info"]
            if "gpt-oss.context_length" in model_details:
                capabilities["context_length"] = model_details["gpt-oss.context_length"]
            elif "llama.context_length" in model_details:
                capabilities["context_length"] = model_details["llama.context_length"]
        
        # Check capabilities field if available
        if "capabilities" in model_info:
            caps = model_info["capabilities"]
            if "tools" in caps:
                capabilities["function_calling"] = True
            if "thinking" in caps:
                capabilities["thinking_mode"] = True
        
        return capabilities
    except Exception as e:
        print(f"Error getting capabilities for {model_name}: {e}")
        return {
            "function_calling": False,
            "system_messages": True,
            "streaming": True,
            "context_length": 2048,
            "parameter_size": "unknown",
            "thinking_mode": False
        }

def get_ollama_server_info(base_url="http://localhost:11434"):
    """
    Get information about the Ollama server.
    
    Args:
        base_url (str): The base URL of the Ollama server.
        
    Returns:
        dict: Server information including version, status, etc.
    """
    try:
        # Try to get server version
        response = requests.get(f"{base_url}/api/version")
        response.raise_for_status()
        version_info = response.json()
        
        # Test server connectivity with a simple request
        models_response = requests.get(f"{base_url}/api/tags")
        models_response.raise_for_status()
        
        return {
            "connected": True,
            "version": version_info.get("version", "unknown"),
            "url": base_url,
            "status": "connected"
        }
    except requests.exceptions.ConnectionError:
        return {
            "connected": False,
            "error": "Connection refused - is Ollama running?",
            "url": base_url,
            "status": "connection_error"
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "url": base_url,
            "status": "error"
        }

# Global state for current configuration
_current_config = {
    "selected_model": None,
    "selected_tools": [],
    "thinking_mode": {
        "enabled": False,
        "level": 1
    },
    "parameters": None,  # Will be set dynamically based on selected model
    "base_url": "http://localhost:11434"
}

def set_base_url(url):
    """
    Set the Ollama server base URL.
    
    Args:
        url (str): The base URL of the Ollama server.
    """
    global _current_config
    _current_config["base_url"] = url

def get_current_parameters(model_name=None):
    """
    Get current model parameters, fetching defaults from Ollama if needed.
    
    Args:
        model_name (str): Optional model name to get specific parameters for.
    
    Returns:
        dict: Current parameters configuration.
    """
    global _current_config
    
    # If no parameters set or model changed, get defaults from Ollama
    target_model = model_name or _current_config["selected_model"]
    
    if _current_config["parameters"] is None or _current_config["selected_model"] != target_model:
        if target_model:
            _current_config["parameters"] = get_default_parameters_for_model(target_model, _current_config["base_url"])
            _current_config["selected_model"] = target_model
        else:
            # Return generic defaults if no model specified
            _current_config["parameters"] = {
                "temperature": 0.8,
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "num_ctx": 2048,
            }
    
    return _current_config["parameters"].copy()

def set_parameters(parameters, model_name=None):
    """
    Set model parameters.
    
    Args:
        parameters (dict): Dictionary of parameters to update.
        model_name (str): Optional model name to set parameters for.
        
    Returns:
        dict: Updated parameters.
    """
    global _current_config
    
    # Ensure we have base parameters first
    current_params = get_current_parameters(model_name)
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

def send_message_to_ollama_model(model, message, stream=False, base_url=None, use_tools=True, system_message=""):
    """
    Sends a message to a specified Ollama model and returns the response.

    Args:
        model (str): The name of the model to use.
        message (str): The message to send.
        stream (bool): Whether to stream the response or get the full output.
        base_url (str): The base URL of the Ollama server (optional).
        use_tools (bool): Whether to include selected tools in the request.
        system_message (str): System message to include.

    Returns:
        str or generator: The full response as a string, or a generator yielding streamed chunks.
    """
    if base_url is None:
        base_url = _current_config["base_url"]
        
    url = f"{base_url}/api/generate"
    
    # Get current parameters for this model
    parameters = get_current_parameters(model)
    
    # Build the payload
    payload = {
        "model": model,
        "prompt": message,
        "stream": stream,
        "options": parameters
    }
    
    # Handle thinking mode and system message
    thinking_config = get_thinking_mode()
    
    if thinking_config["enabled"]:
        # Enable thinking mode
        level_map = {1: "low", 2: "medium", 3: "high"}
        thinking_level = level_map.get(thinking_config["level"], "medium")
        payload["prompt"] = f"[THINKING_MODE: {thinking_level}] {message}"
        
        # Add system message for thinking mode
        thinking_system = "You may use <think></think> tags to show your reasoning process when helpful."
        if system_message:
            payload["system"] = f"{system_message} {thinking_system}"
        else:
            payload["system"] = thinking_system
            
        print(f"🧠 Thinking mode enabled (level: {thinking_level})")
    else:
        # Disable thinking mode - explicitly suppress thinking
        payload["prompt"] = message
        
        # Add system message that suppresses thinking
        no_thinking_system = "Respond directly without showing your internal reasoning or using <think></think> tags. Provide clear, concise answers."
        if system_message:
            payload["system"] = f"{system_message} {no_thinking_system}"
        else:
            payload["system"] = no_thinking_system
            
        print("🚫 Thinking mode disabled - direct response mode")
    
    try:
        response = requests.post(url, json=payload, stream=stream)
        response.raise_for_status()
        
        if stream:
            def stream_generator():
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            if 'response' in data:
                                yield data['response']
                        except json.JSONDecodeError:
                            continue
            return stream_generator()
        else:
            data = response.json()
            response_text = data.get('response', '')
            
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
    cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)  # Replace multiple newlines with double newline
    cleaned = cleaned.strip()
    
    return cleaned

def get_full_config():
    """
    Get complete current configuration.
    
    Returns:
        dict: Full configuration including server, parameters, tools, etc.
    """
    global _current_config
    
    try:
        server_info = get_ollama_server_info(_current_config["base_url"])

        
        return {
            "server": server_info,
            "parameters": _current_config["parameters"],
            "thinking_mode": _current_config["thinking_mode"],
            "selected_model": _current_config["selected_model"],
            "base_url": _current_config["base_url"]
        }
    except Exception as e:
        return {
            "error": f"Error getting configuration: {str(e)}",
            "base_url": _current_config["base_url"]
        }

# Example usage:
if __name__ == "__main__":
    # Test server connection
    server_info = get_ollama_server_info()
    print(f"Server info: {server_info}")
    
    # Test fetching models
    models = fetch_local_ollama_models()
    print(f"Available models: {[m['name'] for m in models]}")
    
    if models:
        # Test model info
        first_model = models[0]['name']
        model_info = get_model_info(first_model)
        print(f"Model info for {first_model}: {model_info}")
        
        # Test capabilities
        capabilities = get_model_capabilities(first_model)
        print(f"Capabilities for {first_model}: {capabilities}")
        
        # Test default parameters
        params = get_default_parameters_for_model(first_model)
        print(f"Default parameters: {params}")
    
    # Test thinking mode
    set_thinking_mode(True, 2)
    thinking = get_thinking_mode()
    print(f"Thinking mode: {thinking}")
    
    # Test full config
    config = get_full_config()
    print(f"Full config keys: {list(config.keys())}")