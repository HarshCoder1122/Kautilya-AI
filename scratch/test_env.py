import os
import json
from dotenv import load_dotenv

# Try to load the dotenv file
env_path = os.path.join(os.path.dirname(__file__), '../backend/.env')
print(f"Loading env from: {env_path}")
load_dotenv(env_path)

sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
if not sa_json:
    print("Error: FIREBASE_SERVICE_ACCOUNT_JSON not found in env!")
else:
    print("Successfully retrieved FIREBASE_SERVICE_ACCOUNT_JSON.")
    try:
        data = json.loads(sa_json)
        print("Success: JSON loaded correctly!")
        print(f"Project ID: {data.get('project_id')}")
        print(f"Private Key (start): {data.get('private_key')[:50]}...")
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Value: {sa_json[:100]}...")
