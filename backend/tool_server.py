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
from tool_search import ToolSearchEngine
from docker_executor import DockerToolExecutor

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
        self.bugged_tools: Dict[str, Dict[str, Any]] = {}  # NEW: Track buggy tools
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
    
    def mark_tool_as_bugged(self, tool_name: str, error_details: Dict[str, Any]):
        """Mark a tool as bugged"""
        if tool_name in self.tools:
            tool = self.tools[tool_name]
            if tool_name not in self.bugged_tools:
                self.bugged_tools[tool_name] = {
                    'tool_info': tool,
                    'failures': [],
                    'first_failure': datetime.utcnow().isoformat()
                }
            
            self.bugged_tools[tool_name]['failures'].append({
                'timestamp': datetime.utcnow().isoformat(),
                'error': error_details
            })
            
            logger.warning(f"⚠️ Tool '{tool_name}' marked as bugged (failures: {len(self.bugged_tools[tool_name]['failures'])})")
    
    def is_tool_bugged(self, tool_name: str) -> bool:
        """Check if a tool is marked as bugged"""
        return tool_name in self.bugged_tools
    
    def get_bugged_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all bugged tools"""
        return self.bugged_tools.copy()
    
    def clear_tool_bug_status(self, tool_name: str):
        """Clear bug status for a tool"""
        if tool_name in self.bugged_tools:
            del self.bugged_tools[tool_name]
            logger.info(f"✓ Bug status cleared for tool '{tool_name}'")
    
    def list_tools(self, include_unavailable: bool = False, exclude_bugged: bool = False) -> Dict[str, Any]:
        """List all available tools"""
        tools_list = {}
        
        for name, tool in self.tools.items():
            # Skip bugged tools if requested
            if exclude_bugged and name in self.bugged_tools:
                continue
                
            tools_list[name] = {
                'name': tool['name'],
                'description': tool['description'],
                'category': tool['category'],
                'params': tool['params'],
                'required_params': tool['required_params'],
                'optional_params': tool['optional_params'],
                'tags': tool['tags'],
                'available': True,
                'is_bugged': name in self.bugged_tools
            }
            
            # Add bug info if tool is bugged
            if name in self.bugged_tools:
                tools_list[name]['bug_count'] = len(self.bugged_tools[name]['failures'])
                tools_list[name]['last_failure'] = self.bugged_tools[name]['failures'][-1]['timestamp']
        
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
                    'is_bugged': False,
                    'error': error
                }
        
        return tools_list
    
    def get_availability_status(self) -> Dict[str, Any]:
        """Get overall tool availability status"""
        return {
            'total_tools': len(self.tools) + len(self.unavailable_tools),
            'available_tools': len(self.tools),
            'unavailable_tools': len(self.unavailable_tools),
            'bugged_tools': len(self.bugged_tools),
            'available_tool_names': list(self.tools.keys()),
            'unavailable_tool_names': list(self.unavailable_tools.keys()),
            'bugged_tool_names': list(self.bugged_tools.keys())
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
         rate_limit: int = None, tags: list = None, requirements: list = None):
    """
    Decorator to mark a function as a tool
    
    Args:
        name: Tool name
        category: Tool category
        auth_required: Whether authentication is required
        rate_limit: Rate limit for this tool
        tags: List of tags for search/categorization
        requirements: List of pip packages required for Docker execution
    """
    def decorator(func):
        func._is_tool = True
        func._tool_name = name or func.__name__
        func._tool_category = category
        func._auth_required = auth_required
        func._rate_limit = rate_limit
        func._tags = tags or []
        func._requirements = requirements or []
        return func
    return decorator

# Initialize tool registry and Docker executor
registry = ToolRegistry()
search_engine = ToolSearchEngine(registry)
docker_executor = DockerToolExecutor()

# Pull base image on startup - only in main process, not reloader
if docker_executor.is_available() and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    logger.info("Pulling Docker base image...")
    docker_executor.pull_base_image()

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
# ONLY in the main reloader process to avoid multiple hash generations
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    USERS = {
        'admin': generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123'))
    }
    logger.info(f"Admin user hash generated: {USERS['admin'][:50]}...")
else:
    # In parent reloader process, use placeholder
    USERS = {
        'admin': generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123'))
    }

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
    
    # Check if tool is bugged
    if registry.is_tool_bugged(tool_name):
        bug_info = registry.bugged_tools[tool_name]
        return jsonify({
            'success': False,
            'error': f"Tool '{tool_name}' is marked as bugged",
            'is_bugged': True,
            'failure_count': len(bug_info['failures']),
            'last_failure': bug_info['failures'][-1]['timestamp'],
            'last_error': bug_info['failures'][-1]['error']
        }), 503
    
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
    use_docker = request.args.get('use_docker', 'true').lower() == 'true'
    
    # Execute tool
    try:
        docker_result = None
        docker_error = None
        executed_in_docker = False
        
        if use_docker and docker_executor.is_available():
            try:
                # Get tool source code
                import inspect
                tool_source = inspect.getsource(tool['function'])
                
                # Extract requirements if specified
                requirements = getattr(tool['function'], '_requirements', None)
                
                # Execute in Docker
                docker_result = docker_executor.execute_tool(
                    tool_code=tool_source,
                    tool_name=tool['name'],
                    params=params,
                    timeout=int(request.args.get('timeout', 30)),
                    requirements=requirements
                )
                
                # Check if Docker execution was successful
                if docker_result.get('success'):
                    return jsonify({
                        'success': True,
                        'tool': tool_name,
                        'result': docker_result.get('result'),
                        'executed_in_docker': True,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                else:
                    # Docker execution failed, log and fallback
                    docker_error = docker_result.get('error', 'Unknown Docker execution error')
                    logger.warning(f"Docker execution failed for tool '{tool_name}': {docker_error}")
                    logger.info(f"Falling back to direct execution for tool '{tool_name}'")
            except Exception as e:
                # Docker execution threw exception, log and fallback
                docker_error = str(e)
                logger.warning(f"Docker execution exception for tool '{tool_name}': {docker_error}")
                logger.info(f"Falling back to direct execution for tool '{tool_name}'")
        
        # Fallback to direct execution (if Docker wasn't used, failed, or not available)
        try:
            result = registry.execute_tool(tool_name, params)
            
            response = {
                'success': True,
                'tool': tool_name,
                'result': result,
                'executed_in_docker': False,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Include Docker failure info if applicable
            if docker_error:
                response['docker_fallback'] = True
                response['docker_error'] = docker_error
            
            return jsonify(response)
        except Exception as fallback_error:
            # Direct execution also failed - mark as bugged if both failed
            error_msg = str(fallback_error)
            logger.error(f"Direct execution also failed for tool '{tool_name}': {error_msg}")
            logger.error(traceback.format_exc())
            
            # Mark tool as bugged
            registry.mark_tool_as_bugged(tool_name, {
                'docker_error': docker_error,
                'direct_error': error_msg,
                'params': params,
                'traceback': traceback.format_exc()
            })
            
            # Return detailed error with both failures
            error_response = {
                'success': False,
                'error': f'Tool execution failed: {error_msg}',
                'tool': tool_name,
                'is_bugged': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if docker_error:
                error_response['docker_error'] = docker_error
                error_response['docker_attempted'] = True
            
            return jsonify(error_response), 500
        
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

@app.route('/tools/<tool_name>/clear_bug', methods=['POST'])
@require_auth
def clear_tool_bug(tool_name: str):
    """Clear bug status for a tool"""
    registry.clear_tool_bug_status(tool_name)
    return jsonify({
        'success': True,
        'message': f"Bug status cleared for tool '{tool_name}'"
    })

@app.route('/tools/bugged', methods=['GET'])
def get_bugged_tools():
    """Get list of bugged tools"""
    bugged = registry.get_bugged_tools()
    return jsonify({
        'bugged_tools': bugged,
        'count': len(bugged)
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
    
    # Only log startup info in the main reloader process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Run server
        port = int(os.getenv('TOOL_SERVER_PORT', 5001))
        debug = os.getenv('FLASK_ENV') == 'development'
        
        logger.info(f"Starting Tool Server on port {port}")
        logger.info(f"Debug mode: {debug}")
        logger.info(f"Loaded {len(registry.tools)} tools")
        
        if registry.unavailable_tools:
            logger.warning(f"Failed to load {len(registry.unavailable_tools)} tools")

    # Run the app
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('TOOL_SERVER_PORT', 5001)),
        debug=os.getenv('FLASK_ENV') == 'development',
        use_reloader=os.getenv('FLASK_ENV') == 'development'
    )