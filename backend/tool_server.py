from flask import Flask, request, jsonify
from functools import wraps
import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
import traceback
from datetime import datetime
import logging
import jwt
from dotenv import load_dotenv
import json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('TOOL_SERVER_SECRET')
if not app.config['SECRET_KEY']:
    logger.warning("TOOL_SERVER_SECRET not set in environment, using default (NOT SECURE!)")
    app.config['SECRET_KEY'] = 'your-secret-key-change-this'

class ToolRegistry:
    """Registry to manage dynamically loaded tools and track availability"""
    
    def __init__(self, tools_directory: str = "./tools"):
        self.tools_directory = Path(tools_directory)
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.unavailable_tools: Dict[str, str] = {}  # tool_name -> error_message
        self._load_tools()
    
    def _load_tools(self):
        """Dynamically discover and load tools from the tools directory"""
        if not self.tools_directory.exists():
            self.tools_directory.mkdir(parents=True)
            logger.info(f"Created tools directory: {self.tools_directory}")
            return
        
        # Add tools directory to Python path
        sys.path.insert(0, str(self.tools_directory))
        
        # Discover all Python files in tools directory
        for tool_file in self.tools_directory.glob("*.py"):
            if tool_file.name.startswith("_"):
                continue
            
            try:
                module_name = tool_file.stem
                module = importlib.import_module(module_name)
                
                # Look for functions decorated with @tool
                for name, obj in inspect.getmembers(module):
                    if callable(obj) and hasattr(obj, '_is_tool'):
                        try:
                            tool_info = self._extract_tool_info(obj, module_name)
                            self.tools[tool_info['name']] = tool_info
                            logger.info(f"✓ Loaded tool: {tool_info['name']}")
                        except Exception as e:
                            tool_name = getattr(obj, '_tool_name', name)
                            error_msg = f"Failed to extract tool info: {str(e)}"
                            self.unavailable_tools[tool_name] = error_msg
                            logger.error(f"✗ Failed to load tool '{tool_name}': {error_msg}")
            
            except Exception as e:
                error_msg = f"Failed to import module: {str(e)}"
                self.unavailable_tools[tool_file.stem] = error_msg
                logger.error(f"✗ Failed to load module from {tool_file}: {error_msg}")
                logger.error(traceback.format_exc())
    
    def _extract_tool_info(self, func: Callable, module_name: str) -> Dict[str, Any]:
        """Extract metadata from tool function"""
        sig = inspect.signature(func)
        
        # Get parameters info
        params = {}
        required_params = []
        optional_params = {}
        
        for param_name, param in sig.parameters.items():
            param_info = {
                'type': param.annotation.__name__ if param.annotation != inspect.Parameter.empty else 'Any',
                'required': param.default == inspect.Parameter.empty
            }
            
            if param.default != inspect.Parameter.empty:
                param_info['default'] = param.default
                optional_params[param_name] = param.default
            else:
                required_params.append(param_name)
            
            params[param_name] = param_info
        
        return {
            'name': func._tool_name,
            'function': func,
            'description': func.__doc__ or "No description provided",
            'module': module_name,
            'category': getattr(func, '_tool_category', 'general'),
            'params': params,
            'required_params': required_params,
            'optional_params': optional_params,
            'auth_required': getattr(func, '_auth_required', False),
            'rate_limit': getattr(func, '_rate_limit', None),
            'tags': getattr(func, '_tags', []),
            'available': True
        }
    
    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool by name"""
        return self.tools.get(tool_name)
    
    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is locally available"""
        return tool_name in self.tools
    
    def get_unavailable_tools(self) -> Dict[str, str]:
        """Get list of tools that failed to load with error messages"""
        return self.unavailable_tools.copy()
    
    def list_tools(self, include_unavailable: bool = False) -> Dict[str, Any]:
        """List all available tools"""
        tools_list = {
            name: {
                'name': tool['name'],
                'description': tool['description'],
                'category': tool['category'],
                'params': tool['params'],
                'required_params': tool['required_params'],
                'optional_params': tool['optional_params'],
                'tags': tool['tags'],
                'available': True
            }
            for name, tool in self.tools.items()
        }
        
        if include_unavailable:
            for tool_name, error in self.unavailable_tools.items():
                tools_list[tool_name] = {
                    'name': tool_name,
                    'description': 'Tool failed to load',
                    'category': 'unknown',
                    'params': {},
                    'required_params': [],
                    'optional_params': {},
                    'tags': [],
                    'available': False,
                    'error': error
                }
        
        return tools_list
    
    def get_availability_status(self) -> Dict[str, Any]:
        """Get overall tool availability status"""
        return {
            'total_tools': len(self.tools) + len(self.unavailable_tools),
            'available_tools': len(self.tools),
            'unavailable_tools': len(self.unavailable_tools),
            'available_tool_names': list(self.tools.keys()),
            'unavailable_tool_names': list(self.unavailable_tools.keys())
        }
    
    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a tool with given parameters"""
        tool = self.get_tool(tool_name)
        if not tool:
            if tool_name in self.unavailable_tools:
                raise ValueError(f"Tool '{tool_name}' is not available: {self.unavailable_tools[tool_name]}")
            raise ValueError(f"Tool '{tool_name}' not found")
        
        # Validate required parameters
        missing_params = [p for p in tool['required_params'] if p not in params]
        if missing_params:
            raise ValueError(f"Missing required parameters: {missing_params}")
        
        # Execute the tool function
        try:
            result = tool['function'](**params)
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {str(e)}")
            logger.error(traceback.format_exc())
            raise

# Tool decorator
def tool(name: str = None, category: str = "general", auth_required: bool = False, 
         rate_limit: int = None, tags: list = None):
    """Decorator to mark a function as a tool"""
    def decorator(func):
        func._is_tool = True
        func._tool_name = name or func.__name__
        func._tool_category = category
        func._auth_required = auth_required
        func._rate_limit = rate_limit
        func._tags = tags or []
        return func
    return decorator

# Initialize tool registry
registry = ToolRegistry()

# Authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'No authorization token provided'}), 401
        
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            # Verify JWT token
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

# User authentication (in production, use a proper database)
# Generate password hash ONCE at module load time
USERS = {
    'admin': generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123'))
}

# Add debug logging
logger.info(f"Admin user hash generated: {USERS['admin'][:50]}...")

@app.route('/auth/login', methods=['POST'])
def login():
    """Login and get JWT token"""
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    logger.info(f"Login attempt for user: {username}")
    
    # Check if user exists
    if username not in USERS:
        logger.warning(f"User not found: {username}")
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Check password against stored hash
    stored_hash = USERS[username]
    is_valid = check_password_hash(stored_hash, password)
    
    logger.info(f"Password verification result: {is_valid}")
    
    if not is_valid:
        logger.warning(f"Invalid password for user: {username}")
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Generate JWT token
    token_expiry = int(os.getenv('TOKEN_EXPIRY_HOURS', 24))
    payload = {
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=token_expiry),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    
    logger.info(f"✓ Successful login for user: {username}")
    
    return jsonify({
        'success': True,
        'token': token,
        'token_type': 'Bearer',
        'expires_in': token_expiry * 3600  # seconds
    })

@app.route('/auth/verify', methods=['GET'])
@require_auth
def verify_token():
    """Verify if token is valid"""
    return jsonify({
        'valid': True,
        'user': request.user
    })

# API Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    status = registry.get_availability_status()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'tools': status
    })

@app.route('/tools', methods=['GET'])
def list_tools():
    """List all available tools"""
    include_unavailable = request.args.get('include_unavailable', 'false').lower() == 'true'
    return jsonify({
        'tools': registry.list_tools(include_unavailable=include_unavailable),
        'availability': registry.get_availability_status()
    })

@app.route('/tools/availability', methods=['GET'])
def get_tool_availability():
    """Get tool availability status"""
    return jsonify(registry.get_availability_status())

@app.route('/tools/<tool_name>', methods=['GET'])
def get_tool_info(tool_name: str):
    """Get detailed information about a specific tool"""
    tool = registry.get_tool(tool_name)
    
    if not tool:
        # Check if it's an unavailable tool
        if tool_name in registry.unavailable_tools:
            return jsonify({
                'error': f"Tool '{tool_name}' is not available",
                'reason': registry.unavailable_tools[tool_name],
                'available': False
            }), 503  # Service Unavailable
        
        return jsonify({'error': f"Tool '{tool_name}' not found"}), 404
    
    return jsonify({
        'name': tool['name'],
        'description': tool['description'],
        'category': tool['category'],
        'params': tool['params'],
        'required_params': tool['required_params'],
        'optional_params': tool['optional_params'],
        'auth_required': tool['auth_required'],
        'tags': tool['tags'],
        'available': True
    })

@app.route('/tools/<tool_name>/execute', methods=['POST'])
def execute_tool(tool_name: str):
    """Execute a tool with provided parameters"""
    tool = registry.get_tool(tool_name)
    
    if not tool:
        # Check if it's an unavailable tool
        if tool_name in registry.unavailable_tools:
            return jsonify({
                'success': False,
                'error': f"Tool '{tool_name}' is not available",
                'reason': registry.unavailable_tools[tool_name]
            }), 503
        
        return jsonify({
            'success': False,
            'error': f"Tool '{tool_name}' not found"
        }), 404
    
    # Check if authentication is required
    if tool['auth_required']:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid authentication token'}), 401
    
    # Get parameters from request
    params = request.get_json() or {}
    
    # Execute tool
    try:
        result = registry.execute_tool(tool_name, params)
        return jsonify({
            'success': True,
            'tool': tool_name,
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Tool execution error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error during tool execution',
            'details': str(e)
        }), 500

@app.route('/tools/reload', methods=['POST'])
@require_auth
def reload_tools():
    """Reload all tools from the tools directory"""
    global registry
    registry = ToolRegistry()
    return jsonify({
        'success': True,
        'message': 'Tools reloaded successfully',
        'availability': registry.get_availability_status()
    })

@app.route('/tools/context', methods=['GET'])
def get_tools_context():
    """Generate LLM-friendly context about available tools"""
    category = request.args.get('category')
    
    tools = registry.list_tools()
    if category:
        tools = {k: v for k, v in tools.items() if v.get('category') == category and v.get('available', False)}
    else:
        # Only include available tools
        tools = {k: v for k, v in tools.items() if v.get('available', False)}
    
    context = "Available Tools:\n\n"
    for tool_name, tool_info in tools.items():
        context += f"Tool: {tool_info['name']}\n"
        context += f"Description: {tool_info['description']}\n"
        context += f"Category: {tool_info['category']}\n"
        context += f"Required Parameters: {tool_info['required_params']}\n"
        context += f"Optional Parameters: {tool_info['optional_params']}\n"
        if tool_info['tags']:
            context += f"Tags: {', '.join(tool_info['tags'])}\n"
        context += "\n"
    
    unavailable = registry.get_unavailable_tools()
    if unavailable:
        context += "\nUnavailable Tools:\n"
        for tool_name, error in unavailable.items():
            context += f"- {tool_name}: {error}\n"
    
    return jsonify({
        'context': context,
        'available_tools_count': len(tools),
        'unavailable_tools_count': len(unavailable)
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create tools directory if it doesn't exist
    os.makedirs('./tools', exist_ok=True)
    
    # Run server
    port = int(os.getenv('TOOL_SERVER_PORT', 5001))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Tool Server on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Loaded {len(registry.tools)} tools")
    
    if registry.unavailable_tools:
        logger.warning(f"Failed to load {len(registry.unavailable_tools)} tools")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )