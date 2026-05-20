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

if __name__ == "__main__":
    download_models()
