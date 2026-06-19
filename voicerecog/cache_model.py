"""Build-time model cache.

Downloads the Nemotron 3.5 streaming ASR ONNX-INT4 weights into the image at
build time so the first real request never blocks on an ~800 MB HF Hub fetch.
NON-FATAL: any failure here just means the runtime downloads on first start.

Model: onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4
  (NVIDIA's official ONNX-INT4 export of nvidia/nemotron-3.5-asr-streaming-0.6b,
   optimized for the 560ms chunk size — sub-second latency on CPU.)
"""
import os
from huggingface_hub import snapshot_download

MODEL_REPO = os.environ.get(
    "ASR_MODEL_REPO", "onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4"
)
TARGET_DIR = os.environ.get("ASR_MODEL_DIR", "/home/user/asr_model")


def main():
    print(f"[cache] Downloading {MODEL_REPO} -> {TARGET_DIR} ...", flush=True)
    try:
        path = snapshot_download(
            repo_id=MODEL_REPO,
            local_dir=TARGET_DIR,
            # Pull everything the genai runtime needs (graphs + .data + tokenizer
            # + genai_config.json). Skip the doc images to keep the layer lean.
            ignore_patterns=["*.png", "*.md"],
        )
        print(f"[cache] Model cached at {path}", flush=True)
        for f in sorted(os.listdir(path)):
            fp = os.path.join(path, f)
            size = os.path.getsize(fp) if os.path.isfile(fp) else 0
            print(f"[cache]   {f} ({size // (1024 * 1024)} MB)", flush=True)
    except Exception as e:
        print(f"[cache] WARN: snapshot failed (will download at runtime): {e}", flush=True)


if __name__ == "__main__":
    main()