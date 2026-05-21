import os
from huggingface_hub import HfApi, whoami

api = HfApi()
try:
    user = whoami()
    print("HF Auth Check:")
    print(f"Logged in as: {user.get('username')}")
    print(f"Auth type: {user.get('auth', {}).get('type')}")
except Exception as e:
    print(f"HF Auth failed/not logged in: {e}")

try:
    print("\nFetching space metadata...")
    space_info = api.space_info(repo_id="HarshSharma1212/KAUTILYABACKEND")
    print(f"Space Repo ID: {space_info.id}")
    print(f"Space SDK: {space_info.sdk}")
    print(f"Space Status: {space_info.runtime.stage if space_info.runtime else 'Unknown'}")
except Exception as e:
    print(f"Failed to fetch space info: {e}")
