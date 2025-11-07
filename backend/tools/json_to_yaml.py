# filepath: /home/vardhin/Documents/git/Rhea/backend/tools/json_to_yaml.py
from tool_server import tool
import json
import yaml

@tool(name="json_to_yaml", category="data", tags=["json", "yaml", "conversion", "data"])
def convert_json_to_yaml(json_string: str) -> str:
    """Converts a JSON string to a YAML string."""
    try:
        data = json.loads(json_string)
        yaml_string = yaml.safe_dump(data, indent=2, default_flow_style=False)
        return yaml_string
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON string provided.")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred during YAML conversion: {e}")