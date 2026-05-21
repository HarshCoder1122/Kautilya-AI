import os
import sys
import json

backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.append(backend_path)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, '.env'))
load_dotenv()

from extensions import db

if not db:
    print("Firestore not initialized.")
    sys.exit(1)

print("--- USERS COLLECTION ---")
try:
    users = db.collection('users').stream()
    for doc in users:
        print(f"UID: {doc.id} -> {doc.to_dict()}")
except Exception as e:
    print(f"Error streaming users: {e}")

print("--- PRO USERS COLLECTION ---")
try:
    pro_users = db.collection('pro_users').stream()
    for doc in pro_users:
        print(f"UID: {doc.id} -> {doc.to_dict()}")
except Exception as e:
    print(f"Error streaming pro_users: {e}")
