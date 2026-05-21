import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from extensions import db

if not db:
    print("Database not connected!")
    sys.exit(1)

print("--- PRO USERS ---")
pro_users = db.collection('pro_users').stream()
for u in pro_users:
    print(f"UID: {u.id} | data: {u.to_dict()}")

print("\n--- USER RECORD FOR cBylypg52cTDhf4NLfxeMEGxGzw1 ---")
user_doc = db.collection('users').document('cBylypg52cTDhf4NLfxeMEGxGzw1').get()
if user_doc.exists:
    print(f"Exists: {user_doc.to_dict()}")
else:
    print("Does not exist in 'users' collection.")

user_credits = db.collection('user_credits').document('cBylypg52cTDhf4NLfxeMEGxGzw1').get()
if user_credits.exists:
    print(f"Credits: {user_credits.to_dict()}")
else:
    print("No credits record.")
