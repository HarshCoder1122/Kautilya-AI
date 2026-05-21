import os
from huggingface_hub import HfApi

api = HfApi()
try:
    print("Listing files in HarshSharma1212/KAUTILYABACKEND space...")
    files = api.list_repo_files(repo_id="HarshSharma1212/KAUTILYABACKEND", repo_type="space")
    print("Files found in space:")
    for f in files[:30]:
        print(f"  - {f}")
    if len(files) > 30:
        print(f"  ... and {len(files) - 30} more files")
except Exception as e:
    print(f"Failed to list files: {e}")
