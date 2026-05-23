import os
from huggingface_hub import HfApi

api = HfApi()
repo_id = "HarshSharma1212/KautilyaVoice"

def upload_voice():
    print(f"Uploading services folder to {repo_id}...")
    try:
        api.upload_folder(
            folder_path="./scratch/scratch/livekit_space/services",
            path_in_repo="services",
            repo_id=repo_id,
            repo_type="space",
            ignore_patterns=["**/__pycache__/*", "*.log"]
        )
        print("[SUCCESS] services folder uploaded.")
    except Exception as e:
        print(f"[ERROR] services folder upload failed: {e}")

    files = ["Dockerfile", "config.py", "main.py", "requirements.txt", "system_prompt_cloud.txt", "system_prompts.py"]
    for f in files:
        local_path = f"./scratch/scratch/livekit_space/{f}"
        if os.path.exists(local_path):
            print(f"Uploading {f}...")
            try:
                api.upload_file(
                    path_or_fileobj=local_path,
                    path_in_repo=f,
                    repo_id=repo_id,
                    repo_type="space"
                )
                print(f"[SUCCESS] {f} uploaded.")
            except Exception as e:
                print(f"[ERROR] Failed to upload {f}: {e}")
        else:
            print(f"[WARNING] Local file {local_path} does not exist!")

if __name__ == "__main__":
    upload_voice()
