import sys
from huggingface_hub import HfApi

api = HfApi()
repo_id = "HarshSharma1212/KAUTILYABACKEND"

try:
    files = api.list_repo_files(repo_id=repo_id, repo_type="space")
    print(f"Files in {repo_id}:")
    for f in sorted(files):
         print(f"- {f}")
except Exception as e:
    print(f"Error: {e}")
