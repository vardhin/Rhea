from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

# Test password
test_password = 'admin123'
env_password = os.getenv('ADMIN_PASSWORD', 'admin123')

print(f"Test password: {test_password}")
print(f"ENV password: {env_password}")
print(f"Passwords match: {test_password == env_password}")

# Generate hash
password_hash = generate_password_hash(env_password)
print(f"\nGenerated hash: {password_hash}")

# Test verification
is_valid = check_password_hash(password_hash, test_password)
print(f"Hash verification result: {is_valid}")

# Check what's currently in tool_server.py
print("\n" + "="*50)
print("Make sure your tool_server.py has:")
print("="*50)
print(f"""
USERS = {{
    'admin': generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123'))
}}
""")