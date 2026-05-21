import os
import sys

backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.append(backend_path)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, '.env'))
load_dotenv()

from extensions import db
import firebase_admin
from firebase_admin import auth

if not firebase_admin._apps:
    print("Firebase admin not initialized.")
    sys.exit(1)

print("--- FIREBASE AUTH USERS ---")
try:
    page = auth.list_users()
    for user in page.users:
        print(f"UID: {user.uid} | Email: {user.email} | Display Name: {user.display_name}")
except Exception as e:
    print(f"Error listing auth users: {e}")
