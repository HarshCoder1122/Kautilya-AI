from kokoro import KPipeline

def download_models():
    print("Caching Kokoro (English)...")
    try:
        pipeline_en = KPipeline(lang_code='a')
        en_voices = ['af_heart', 'af_bella', 'af_nicole', 'af_sky', 'am_adam', 'am_michael']
        for v in en_voices:
            try:
                pipeline_en.load_voice(v)
            except:
                pass
        print("Kokoro English cached successfully.")
    except Exception as e:
        print(f"Error caching Kokoro English: {e}")

    print("Caching Kokoro (Hindi)...")
    try:
        pipeline_hi = KPipeline(lang_code='h')
        hi_voices = ['hf_alpha', 'hf_beta', 'hm_omega', 'hm_psi']
        for v in hi_voices:
            try:
                pipeline_hi.load_voice(v)
                print(f"  cached Hindi voice: {v}")
            except Exception as ve:
                print(f"  skipped Hindi voice {v}: {ve}")
        print("Kokoro Hindi cached successfully.")
    except Exception as e:
        print(f"Error caching Kokoro Hindi: {e}")

def download_onnx():
    """Pre-cache the fast ONNX engine's model + voices at build time.
    int8 model = ~2x faster than fp32 on CPU. NON-FATAL: any failure just means
    the runtime downloads it on first start (or falls back to PyTorch)."""
    import os, urllib.request
    gh = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
    files = {
        # int8 quantized (fastest on CPU)
        "kokoro-int8.onnx": "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/onnx/model_quantized.onnx",
        "voices-v1.0.bin":  gh + "voices-v1.0.bin",
    }
    for fn, url in files.items():
        try:
            if os.path.exists(fn) and os.path.getsize(fn) > 0:
                print(f"ONNX {fn} already present.")
                continue
            print(f"Downloading ONNX {fn} ...")
            urllib.request.urlretrieve(url, fn)
            print(f"  saved {fn} ({os.path.getsize(fn)//(1024*1024)} MB)")
        except Exception as e:
            print(f"  ONNX download skipped {fn}: {e}")

if __name__ == "__main__":
    download_models()
    download_onnx()
