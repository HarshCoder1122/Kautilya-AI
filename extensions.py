"""
Kautilya AI — Shared Singletons & Extension Init
Initializes Firebase, Firestore, Razorpay, LimitManager, VectorStore.
All modules import these shared instances from here.
"""
import os
import json
import logging

import razorpay

from config import (
    RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET,
    CHAT_DATA_DIR, GEMINI_API_KEYS,
)

# ============== Logging ==============
handler = logging.FileHandler('jarvis.log')
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)

# Suppress curl_cffi warnings
class FilterCurlCffiWarnings(logging.Filter):
    def filter(self, record):
        return "Impersonate" not in record.getMessage()

logging.getLogger("curl_cffi").addFilter(FilterCurlCffiWarnings())
logging.getLogger("curl_cffi").setLevel(logging.ERROR)

# ============== Firebase Admin ==============
FIREBASE_AVAILABLE = False
db = None

try:
    import firebase_admin
    from firebase_admin import credentials, auth as firebase_auth, firestore

    if not firebase_admin._apps:
        # 1. Try environment variable (Standard practice for cloud deployments)
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if sa_json:
            try:
                info = json.loads(sa_json)
                cred = credentials.Certificate(info)
                firebase_admin.initialize_app(cred)
                print("[EXTENSIONS] Firebase Admin: OK (Loaded from ENV)")
            except json.JSONDecodeError:
                if os.path.exists(sa_json):
                    cred = credentials.Certificate(sa_json)
                    firebase_admin.initialize_app(cred)
                    print(f"[EXTENSIONS] Firebase Admin: OK (Loaded from Path in ENV)")

        # 2. ADC Fallback
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
                print("[EXTENSIONS] Firebase Admin: OK (Using ADC)")
            except:
                print("[EXTENSIONS] Firebase Admin: Error (No credentials found)")

    if firebase_admin._apps:
        FIREBASE_AVAILABLE = True
        db = firestore.client()
        print("[EXTENSIONS] Firestore: Connected")

except ImportError:
    print("[EXTENSIONS] firebase-admin not installed — Firestore disabled")
except Exception as e:
    print(f"[EXTENSIONS] Firebase Admin init failed: {e}")

# ============== LimitManager ==============
from limits_manager import LimitManager

limit_manager = LimitManager(data_dir=CHAT_DATA_DIR)
if db:
    limit_manager.set_db(db)
    print("[EXTENSIONS] LimitManager: Firestore connected")

# ============== Razorpay ==============
razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    print("[EXTENSIONS] Razorpay: OK")

# ============== VectorStore ==============
from services.vector_store_service import VectorStore

vector_store = VectorStore()
print("[EXTENSIONS] VectorStore: Initialized")

print(f"[EXTENSIONS] All singletons ready. Firebase={FIREBASE_AVAILABLE}")
