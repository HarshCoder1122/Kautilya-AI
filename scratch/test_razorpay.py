import os
import sys

backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.append(backend_path)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, '.env'))
load_dotenv()

import razorpay

key_id = os.environ.get('RAZORPAY_KEY_ID', '')
key_secret = os.environ.get('RAZORPAY_KEY_SECRET', '')
plan_id = os.environ.get('RAZORPAY_PRO_PLAN_ID', 'plan_JarvisPro599')

print(f"RAZORPAY_KEY_ID: {key_id[:6]}... (length={len(key_id)})")
print(f"RAZORPAY_KEY_SECRET: {key_secret[:6]}... (length={len(key_secret)})")
print(f"RAZORPAY_PRO_PLAN_ID: {plan_id}")

if not key_id or not key_secret:
    print("Error: Razorpay credentials are empty in this environment.")
    sys.exit(1)

client = razorpay.Client(auth=(key_id, key_secret))
try:
    print("Testing subscription creation...")
    subscription = client.subscription.create({
        'plan_id': plan_id,
        'customer_notify': 1,
        'total_count': 120,
        'notes': {'uid': 'test_uid', 'plan_type': 'pro'}
    })
    print("Subscription created successfully!")
    print(subscription)
except Exception as e:
    print(f"Error creating subscription: {e}")
    print(f"Error type: {type(e)}")
