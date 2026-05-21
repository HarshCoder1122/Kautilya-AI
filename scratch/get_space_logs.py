import os
import sys
from huggingface_hub import HfApi

api = HfApi()
try:
    print("Fetching logs from HarshSharma1212/KAUTILYABACKEND...", flush=True)
    # Read space logs
    for line in api.fetch_space_logs(repo_id="HarshSharma1212/KAUTILYABACKEND"):
        sys.stdout.buffer.write(line.encode('utf-8'))
        sys.stdout.flush()
except Exception as e:
    print(f"Failed to fetch logs: {e}", flush=True)
