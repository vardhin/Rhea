import docker
import json
import tempfile
import os
from pathlib import Path
import logging
from typing import Dict, Any, Optional
import traceback

logger = logging.getLogger(__name__)

class DockerToolExecutor:
    """Execute tools in isolated Docker containers"""
    
    def __init__(self, base_image: str = "python:3.11-slim"):
        self.base_image = base_image
        self.client = None
        self.error_message = None
        self._initialize_docker()
    
    def _initialize_docker(self):
        """Initialize Docker client"""
        try:
            self.client = docker.from_env()
            # Test connection
            self.client.ping()
            logger.info("✓ Docker client initialized successfully")
            self.error_message = None
        except docker.errors.DockerException as e:
            error_str = str(e)
            logger.error(f"✗ Failed to initialize Docker client: {error_str}")
            
            if "Permission denied" in error_str or "PermissionError" in error_str:
                self.error_message = (
                    "Permission denied connecting to Docker socket. "
                    "Run: sudo usermod -aG docker $USER && newgrp docker"
                )
            elif "Connection refused" in error_str:
                self.error_message = (
                    "Docker daemon is not running. "
                    "Run: sudo systemctl start docker"
                )
            elif "No such file or directory" in error_str:
                self.error_message = (
                    "Docker is not installed or socket not found. "
                    "Install Docker and ensure it's running."
                )
            else:
                self.error_message = f"Docker connection failed: {error_str}"
            
            logger.error(self.error_message)
            self.client = None
        except Exception as e:
            self.error_message = f"Unexpected error initializing Docker: {str(e)}"
            logger.error(self.error_message)
            logger.error(traceback.format_exc())
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Docker is available"""
        return self.client is not None
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed Docker status"""
        if self.is_available():
            try:
                info = self.client.info()
                return {
                    'available': True,
                    'base_image': self.base_image,
                    'docker_version': info.get('ServerVersion', 'unknown'),
                    'containers_running': info.get('ContainersRunning', 0),
                    'images_count': len(self.client.images.list())
                }
            except Exception as e:
                return {
                    'available': True,
                    'base_image': self.base_image,
                    'error': f'Failed to get Docker info: {str(e)}'
                }
        else:
            return {
                'available': False,
                'base_image': self.base_image,
                'error': self.error_message or 'Docker is not available'
            }
    
    def _create_tool_script(self, tool_code: str, tool_name: str, params: Dict[str, Any], requirements: list = None) -> str:
        """Create executable Python script for the tool"""
        
        # Build import statements based on requirements
        import_statements = []
        if requirements:
            for req in requirements:
                # Handle common package name mappings
                package_name = req.split('[')[0].split('==')[0].split('>=')[0].split('<=')[0].strip()
                import_statements.append(f"import {package_name}")
        
        imports = '\n'.join(import_statements) if import_statements else ''
        
        script = f'''
import sys
import json
import traceback
{imports}

# Tool decorator (needed if tool code references it)
def tool(name=None, category="general", auth_required=False, rate_limit=None, tags=None, requirements=None):
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

# Tool code
{tool_code}

# Execute tool
try:
    params = {json.dumps(params)}
    result = {tool_name}(**params)
    
    # Handle different result types
    if isinstance(result, (dict, list)):
        output = result
    else:
        output = {{"result": result}}
    
    print(json.dumps({{"success": True, "result": output}}))
    sys.exit(0)
    
except Exception as e:
    error_data = {{
        "success": False,
        "error": str(e),
        "traceback": traceback.format_exc()
    }}
    print(json.dumps(error_data), file=sys.stderr)
    sys.exit(1)
'''
        return script
    
    def _create_dockerfile_content(self, requirements: list = None) -> str:
        """Create Dockerfile content for tool execution"""
        reqs = requirements or ["requests"]
        
        dockerfile = f'''FROM {self.base_image}

# Install required packages
RUN pip install --no-cache-dir {' '.join(reqs)}

# Create working directory
WORKDIR /tool

# Copy tool script (will be mounted)
CMD ["python", "/tool/script.py"]
'''
        return dockerfile
    
    def execute_tool(
        self, 
        tool_code: str, 
        tool_name: str, 
        params: Dict[str, Any],
        timeout: int = 30,
        requirements: list = None
    ) -> Dict[str, Any]:
        """
        Execute tool in Docker container
        
        Args:
            tool_code: The tool's Python code
            tool_name: Name of the tool function
            params: Parameters to pass to the tool
            timeout: Execution timeout in seconds
            requirements: List of pip packages to install
        
        Returns:
            Execution result dictionary
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'Docker is not available',
                'executed_in_docker': False
            }
        
        temp_dir = None
        container = None
        
        try:
            # Create temporary directory for tool files
            temp_dir = tempfile.mkdtemp(prefix='tool_exec_')
            temp_path = Path(temp_dir)
            
            # Create tool script with requirements for imports
            script_content = self._create_tool_script(tool_code, tool_name, params, requirements)
            script_path = temp_path / "script.py"
            script_path.write_text(script_content)
            
            logger.info(f"Executing tool '{tool_name}' in Docker container")
            logger.debug(f"Parameters: {params}")
            logger.debug(f"Requirements: {requirements}")
            
            # Prepare pip install command if requirements specified
            pip_install = ""
            if requirements:
                packages = " ".join(requirements)
                pip_install = f"pip install --no-cache-dir {packages} && "
                logger.info(f"Installing packages: {packages}")
            
            # Run container with mounted script
            container = self.client.containers.run(
                self.base_image,
                command=["sh", "-c", f"{pip_install}python /tool/script.py"],
                volumes={
                    str(temp_path): {'bind': '/tool', 'mode': 'ro'}
                },
                remove=False,  # Don't auto-remove so we can get logs
                detach=True,
                network_mode='bridge',  # Allow internet access for API calls and pip
                mem_limit='512m',  # Limit memory
                cpu_period=100000,
                cpu_quota=50000,  # Limit CPU to 50%
            )
            
            # Wait for container to finish
            result = container.wait(timeout=timeout)
            exit_code = result['StatusCode']
            
            # Get output
            output = container.logs().decode('utf-8')
            
            # Add logging for debugging
            logger.debug(f"Container output: {output}")
            logger.debug(f"Exit code: {exit_code}")
            
            # Parse JSON output - look for JSON in the output
            try:
                # Split by lines and find the JSON output
                lines = output.strip().split('\n')
                json_output = None
                
                for line in reversed(lines):  # Start from end to get the final output
                    line = line.strip()
                    if line.startswith('{'):
                        try:
                            json_output = json.loads(line)
                            break
                        except json.JSONDecodeError:
                            continue
                
                if json_output:
                    json_output['executed_in_docker'] = True
                    json_output['exit_code'] = exit_code
                    logger.info(f"✓ Tool '{tool_name}' executed successfully in Docker")
                    return json_output
                else:
                    logger.error(f"No JSON output found in container logs: {output}")
                    return {
                        'success': False,
                        'error': 'Failed to parse tool output',
                        'raw_output': output,
                        'executed_in_docker': True,
                        'exit_code': exit_code
                    }
                
            except Exception as e:
                logger.error(f"Failed to parse tool output: {str(e)}")
                logger.error(f"Output was: {output}")
                return {
                    'success': False,
                    'error': f'Failed to parse tool output: {str(e)}',
                    'raw_output': output,
                    'executed_in_docker': True,
                    'exit_code': exit_code
                }
        
        except docker.errors.ContainerError as e:
            logger.error(f"Container execution error: {str(e)}")
            return {
                'success': False,
                'error': f'Container execution failed: {str(e)}',
                'executed_in_docker': True
            }
        
        except docker.errors.ImageNotFound:
            logger.error(f"Docker image not found: {self.base_image}")
            return {
                'success': False,
                'error': f'Docker image not found: {self.base_image}',
                'executed_in_docker': False
            }
        
        except Exception as e:
            logger.error(f"Docker execution error: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': f'Docker execution failed: {str(e)}',
                'executed_in_docker': True
            }
        
        finally:
            # Cleanup
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
            
            if temp_dir:
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                except:
                    pass
    
    def pull_base_image(self):
        """Pull the base Docker image"""
        if not self.is_available():
            return False
        
        try:
            logger.info(f"Pulling Docker image: {self.base_image}")
            self.client.images.pull(self.base_image)
            logger.info(f"✓ Successfully pulled {self.base_image}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull image: {str(e)}")
            return False