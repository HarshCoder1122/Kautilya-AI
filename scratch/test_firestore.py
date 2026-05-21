import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import extensions
from extensions import db

if not db:
    print("Database not connected!")
    sys.exit(1)

print("Connected to Firestore. Querying users...")
users = db.collection('users').stream()
for user in users:
    d = user.to_dict()
    print(f"\nUID: {user.id}")
    print(f"  Email: {d.get('email')}")
    print(f"  Name: {d.get('name')}")
    print(f"  Active API Key: {d.get('active_api_key')}")
    
    # Query api_usage
    daily_coll = db.collection('api_usage').document(user.id).collection('daily').stream()
    daily_docs = list(daily_coll)
    print(f"  Daily usage documents count: {len(daily_docs)}")
    for doc in daily_docs:
        print(f"    - Doc {doc.id}: {doc.to_dict()}")
