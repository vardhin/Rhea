from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

# Get password from environment or use default
password = os.getenv('ADMIN_PASSWORD', 'admin123')

# Generate hash
password_hash = generate_password_hash(password)

print(f"Password: {password}")
print(f"Hash: {password_hash}")
print(f"\nAdd this to your tool_server.py USERS dict:")
print(f"'admin': '{password_hash}'")