from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

# Get password from environment
env_password = os.getenv('ADMIN_PASSWORD', 'admin123')
test_password = 'admin123'

print(f"Environment ADMIN_PASSWORD: {env_password}")
print(f"Test password: {test_password}")
print(f"Match: {env_password == test_password}")
print()

# Generate hash multiple times to show they're different
print("Generating hashes (they will be different each time):")
for i in range(3):
    hash1 = generate_password_hash(env_password)
    print(f"Hash {i+1}: {hash1[:50]}...")
print()

# But they all verify correctly
hash_to_test = generate_password_hash(env_password)
print(f"Test hash: {hash_to_test[:50]}...")
print(f"Verifies with correct password: {check_password_hash(hash_to_test, test_password)}")
print(f"Verifies with wrong password: {check_password_hash(hash_to_test, 'wrongpass')}")
print()

# The problem: USERS dict is created at module load time
print("="*60)
print("THE ISSUE:")
print("="*60)
print("The USERS dict is created when the module loads.")
print("The hash is generated ONCE and stored in USERS.")
print("Every login attempt should use the SAME stored hash.")
print()
print("Solution: Don't regenerate the hash on every request!")