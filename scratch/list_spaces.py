import sys
from huggingface_hub import HfApi

api = HfApi()
try:
    spaces = api.list_spaces(author="HarshSharma1212")
    print("HF Spaces for HarshSharma1212:")
    for s in spaces:
        print(f"- {s.id} (SDK: {s.sdk})")
except Exception as e:
    print(f"Error listing spaces: {e}")
