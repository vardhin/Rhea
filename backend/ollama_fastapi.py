from fastapi import FastAPI, Query, HTTPException, Body, Path
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
from urllib.parse import unquote
import re

from ollama import chat as ollama_chat  # Rename to avoid conflict

from ollama_module import (
    fetch_local_ollama_models, 
    send_message_to_ollama_model,
    get_model_info,
    get_model_capabilities,
    get_default_parameters_for_model,
    get_ollama_server_info,
    get_available_tools,
    get_current_parameters,
    set_parameters,
    get_selected_tools,
    select_tools,
    get_thinking_mode,
    set_thinking_mode,
    get_full_config,
    set_base_url
)

def get_function_handler(tool_name: str):
    """Get the actual function handler for a tool."""
    # This should map to your actual tool implementations
    # You'll need to implement this based on your ollama_module
    from ollama_module import get_tool_function
    return get_tool_function(tool_name)

app = FastAPI(
    title="Rhea - Ollama AI Assistant API",
    description="Advanced API for interacting with Ollama models with tools and thinking capabilities",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class ChatRequest(BaseModel):
    model: str
    message: str
    stream: bool = False
    use_tools: bool = True
    system_message: str = ""
    thinking_mode: Optional[bool] = None
    thinking_level: Optional[int] = None

class ParametersRequest(BaseModel):
    model: Optional[str] = None
    parameters: Dict[str, Any]

class ToolsRequest(BaseModel):
    tools: List[str]

class ThinkingModeRequest(BaseModel):
    enabled: bool
    level: int = 1

class BaseURLRequest(BaseModel):
    url: str

# === Model Management Endpoints ===

@app.get("/models", summary="Get Available Models")
def get_models():
    """Get list of all available Ollama models."""
    try:
        models = fetch_local_ollama_models()
        return JSONResponse(content={"models": models})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching models: {str(e)}")

@app.get("/models/{model_name:path}/info", summary="Get Model Information")
def get_model_details(model_name: str = Path(..., description="Model name")):
    """Get detailed information about a specific model."""
    try:
        # URL decode the model name
        decoded_model_name = unquote(model_name)
        model_info = get_model_info(decoded_model_name)
        if not model_info:
            raise HTTPException(status_code=404, detail=f"Model '{decoded_model_name}' not found")
        return JSONResponse(content={"model_info": model_info})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting model info: {str(e)}")

@app.get("/models/{model_name:path}/capabilities", summary="Get Model Capabilities")
def get_model_caps(model_name: str = Path(..., description="Model name")):
    """Get capabilities of a specific model."""
    try:
        # URL decode the model name
        decoded_model_name = unquote(model_name)
        capabilities = get_model_capabilities(decoded_model_name)
        return JSONResponse(content={"capabilities": capabilities})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting capabilities: {str(e)}")

@app.get("/models/{model_name:path}/parameters", summary="Get Model Default Parameters")
def get_model_params(model_name: str = Path(..., description="Model name")):
    """Get default parameters for a specific model."""
    try:
        # URL decode the model name
        decoded_model_name = unquote(model_name)
        parameters = get_default_parameters_for_model(decoded_model_name)
        return JSONResponse(content={"parameters": parameters})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting parameters: {str(e)}")

# === Chat Endpoints ===

def parse_custom_tool_call(raw_text: str):
    """Parse the custom tool call format into standard JSON."""
    try:
        # Extract the JSON part before the special tokens
        # The format can be: {"name":"time","arguments":{}}<|call|>... or {"command":"time"}<|call|>...
        json_match = re.match(r'^(\{[^<]*\})', raw_text)
        if json_match:
            json_str = json_match.group(1)
            try:
                parsed = json.loads(json_str)
                
                # Handle different formats
                tool_name = None
                tool_args = {}
                
                if 'name' in parsed:
                    tool_name = parsed['name']
                    tool_args = parsed.get('arguments', {})
                elif 'command' in parsed:
                    tool_name = parsed['command']
                    tool_args = parsed.get('arguments', {})
                
                if tool_name:
                    return {
                        'id': f"call_{tool_name}_{hash(raw_text) % 10000}",  # Add unique ID
                        'type': 'function',
                        'function': {
                            'name': tool_name,
                            'arguments': json.dumps(tool_args)
                        }
                    }
            except json.JSONDecodeError:
                pass
        
        # If we can't parse it, return a generic structure with more info
        return {
            'id': 'call_unknown',
            'type': 'function', 
            'function': {
                'name': 'unknown',
                'arguments': json.dumps({'raw': raw_text})
            }
        }
    except Exception:
        return None

@app.post("/chat", summary="Chat with Model")
def chat_endpoint(request: ChatRequest):
    """Send a message to an Ollama model with optional streaming."""
    try:
        # Apply thinking mode if specified in request
        if request.thinking_mode is not None:
            set_thinking_mode(request.thinking_mode, request.thinking_level or 1)
        
        # Get current parameters but filter out valid ones
        current_params = get_current_parameters()
        valid_ollama_params = {
            'temperature', 'top_p', 'top_k', 'repeat_penalty', 'seed',
            'num_ctx', 'num_batch', 'num_gpu', 'main_gpu', 'low_vram',
            'f16_kv', 'logits_all', 'vocab_only', 'use_mmap', 'use_mlock',
            'num_thread', 'num_gqa', 'numa'
        }
        filtered_params = {k: v for k, v in current_params.items() if k in valid_ollama_params}
        
        # Prepare messages in Ollama format
        messages = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.message})
        
        # Get available tools if tool usage is enabled
        tools = None
        if request.use_tools:
            available_tools = get_available_tools()
            selected_tools = get_selected_tools()
            if selected_tools and available_tools:
                # Convert to Ollama tool format
                tools = []
                for tool_name in selected_tools:
                    if tool_name in available_tools:
                        tool_def = available_tools[tool_name]
                        if isinstance(tool_def, dict) and 'function' in tool_def:
                            tools.append(tool_def)
        
        if request.stream:
            def stream_gen():
                try:
                    # Stream response from Ollama WITH tools
                    response = ollama_chat(
                        model=request.model,
                        messages=messages,
                        stream=True,
                        options=filtered_params,
                        tools=tools  # Pass tools so model knows what's available
                    )
                    
                    for chunk in response:
                        # Check if chunk contains tool calls
                        if 'message' in chunk:
                            message = chunk['message']
                            
                            # Stream regular content
                            if 'content' in message and message['content']:
                                yield f"data: {json.dumps({'chunk': message['content'], 'type': 'content'})}\n\n"
                            
                            # Stream tool calls if present
                            if 'tool_calls' in message and message['tool_calls']:
                                for tool_call in message['tool_calls']:
                                    yield f"data: {json.dumps({'tool_call': tool_call, 'type': 'tool_call'})}\n\n"
                
                except Exception as e:
                    error_msg = str(e)
                    
                    # Check if this is a tool call parsing error
                    if "error parsing tool call" in error_msg and "raw=" in error_msg:
                        # Extract the raw tool call data
                        raw_match = re.search(r"raw='([^']*)'", error_msg)
                        if raw_match:
                            raw_tool_call = raw_match.group(1)
                            
                            # Parse the custom tool call format
                            parsed_tool_call = parse_custom_tool_call(raw_tool_call)
                            
                            if parsed_tool_call:
                                # Stream the parsed tool call
                                yield f"data: {json.dumps({'tool_call': parsed_tool_call, 'type': 'tool_call'})}\n\n"
                                # Also provide debug info
                                yield f"data: {json.dumps({'debug': {'raw_tool_call': raw_tool_call, 'parsed': parsed_tool_call}, 'type': 'debug'})}\n\n"
                            else:
                                # If parsing fails, stream the raw data for debugging
                                yield f"data: {json.dumps({'debug': {'raw_tool_call': raw_tool_call, 'parse_failed': True}, 'type': 'debug'})}\n\n"
                        else:
                            # If we can't extract raw data, stream the error
                            yield f"data: {json.dumps({'error': error_msg, 'type': 'error'})}\n\n"
                    else:
                        # For other errors, stream normally
                        yield f"data: {json.dumps({'error': error_msg, 'type': 'error'})}\n\n"
            
            return StreamingResponse(
                stream_gen(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            # Non-streaming response with similar error handling
            try:
                response = ollama_chat(
                    model=request.model,
                    messages=messages,
                    options=filtered_params,
                    tools=tools  # Pass tools so model knows what's available
                )
                
                # Extract response content and tool calls
                message = response.get('message', {})
                response_data = {
                    "response": message.get('content', ''),
                    "tool_calls": message.get('tool_calls', [])
                }
                
                return JSONResponse(content=response_data)
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if this is a tool call parsing error
                if "error parsing tool call" in error_msg and "raw=" in error_msg:
                    # Extract and parse the raw tool call
                    raw_match = re.search(r"raw='([^']*)'", error_msg)
                    if raw_match:
                        raw_tool_call = raw_match.group(1)
                        parsed_tool_call = parse_custom_tool_call(raw_tool_call)
                        
                        return JSONResponse(content={
                            "response": "",
                            "tool_calls": [parsed_tool_call] if parsed_tool_call else [],
                            "debug": {
                                "raw_tool_call": raw_tool_call,
                                "parsed": parsed_tool_call
                            }
                        })
                
                # For other errors, raise normally
                raise HTTPException(status_code=500, detail=f"Error in chat: {error_msg}")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in chat: {str(e)}")

# Legacy endpoint for backward compatibility
@app.post("/chat/simple", summary="Simple Chat (Legacy)")
def simple_chat(
    model: str = Query(..., description="Model name"),
    message: str = Query(..., description="Prompt message"),
    stream: bool = Query(False, description="Stream response")
):
    """Legacy simple chat endpoint."""
    request = ChatRequest(model=model, message=message, stream=stream)
    return chat_endpoint(request)

# === Configuration Endpoints ===

@app.get("/config", summary="Get Full Configuration")
def get_config():
    """Get complete current configuration."""
    try:
        config = get_full_config()
        return JSONResponse(content={"config": config})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting config: {str(e)}")

@app.get("/server/info", summary="Get Server Information")
def get_server_info():
    """Get Ollama server information and status."""
    try:
        server_info = get_ollama_server_info()
        return JSONResponse(content={"server": server_info})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting server info: {str(e)}")

@app.post("/server/url", summary="Set Server URL")
def set_server_url(request: BaseURLRequest):
    """Set the Ollama server base URL."""
    try:
        set_base_url(request.url)
        # Test the new URL
        server_info = get_ollama_server_info()
        return JSONResponse(content={
            "message": f"Base URL set to {request.url}",
            "server": server_info
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting base URL: {str(e)}")

# === Parameters Management ===

@app.get("/parameters", summary="Get Current Parameters")
def get_parameters(model: Optional[str] = Query(None, description="Model name")):
    """Get current model parameters."""
    try:
        parameters = get_current_parameters(model)
        return JSONResponse(content={"parameters": parameters})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting parameters: {str(e)}")

@app.post("/parameters", summary="Set Parameters")
def set_model_parameters(request: ParametersRequest):
    """Set model parameters."""
    try:
        updated_params = set_parameters(request.parameters, request.model)
        return JSONResponse(content={
            "message": "Parameters updated successfully",
            "parameters": updated_params
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting parameters: {str(e)}")

# === Tools Management ===

@app.get("/tools", summary="Get Available Tools")
def get_tools():
    """Get all available tools."""
    try:
        available_tools = get_available_tools()
        selected_tools = get_selected_tools()
        
        # Ensure tools are in the correct format for frontend
        formatted_available = {}
        if isinstance(available_tools, dict):
            for tool_name, tool_def in available_tools.items():
                if isinstance(tool_def, dict) and 'function' in tool_def:
                    formatted_available[tool_name] = tool_def
                else:
                    # If tool_def is not in expected format, create a proper structure
                    formatted_available[tool_name] = {
                        'function': {
                            'name': tool_name,
                            'description': tool_def.get('description', 'No description available') if isinstance(tool_def, dict) else 'No description available',
                            'parameters': tool_def.get('parameters', {}) if isinstance(tool_def, dict) else {}
                        }
                    }
        
        return JSONResponse(content={
            "available": formatted_available,
            "selected": selected_tools
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting tools: {str(e)}")

@app.post("/tools/select", summary="Select Tools")
def select_model_tools(request: ToolsRequest):
    """Select which tools to use with models."""
    try:
        result = select_tools(request.tools)
        return JSONResponse(content={
            "message": "Tools selection updated",
            "selected": result["selected"],
            "available": result["available"]  # Return full available tools object
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error selecting tools: {str(e)}")

@app.get("/tools/selected", summary="Get Selected Tools")
def get_current_tools():
    """Get currently selected tools."""
    try:
        selected = get_selected_tools()
        return JSONResponse(content={"selected_tools": selected})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting selected tools: {str(e)}")

# === Thinking Mode Management ===

@app.get("/thinking", summary="Get Thinking Mode")
def get_current_thinking_mode():
    """Get current thinking mode configuration."""
    try:
        thinking_mode = get_thinking_mode()
        return JSONResponse(content={"thinking_mode": thinking_mode})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting thinking mode: {str(e)}")

@app.post("/thinking", summary="Set Thinking Mode")
def set_model_thinking_mode(request: ThinkingModeRequest):
    """Set thinking mode configuration."""
    try:
        updated_thinking = set_thinking_mode(request.enabled, request.level)
        return JSONResponse(content={
            "message": "Thinking mode updated",
            "thinking_mode": updated_thinking
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting thinking mode: {str(e)}")

# === Health Check ===

@app.get("/health", summary="Health Check")
def health_check():
    """Check if the API and Ollama server are healthy."""
    try:
        server_info = get_ollama_server_info()
        return JSONResponse(content={
            "status": "healthy",
            "api_version": "1.0.0",
            "ollama_server": server_info
        })
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "api_version": "1.0.0"
            }
        )

# === Root endpoint ===

@app.get("/", summary="API Information")
def root():
    """Get API information."""
    return {
        "name": "Rhea - Ollama AI Assistant API",
        "version": "1.0.0",
        "description": "Advanced API for interacting with Ollama models",
        "endpoints": {
            "models": "/models",
            "chat": "/chat",
            "config": "/config",
            "tools": "/tools",
            "thinking": "/thinking",
            "health": "/health",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Rhea API Server...")
    print("📚 Documentation available at: http://localhost:8000/docs")
    print("🔧 Interactive API at: http://localhost:8000/redoc")
    uvicorn.run("ollama_fastapi:app", host="0.0.0.0", port=8000, reload=True)