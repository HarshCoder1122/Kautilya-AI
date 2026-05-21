import os
import sys

backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.append(backend_path)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, '.env'))
load_dotenv()

from flask import Flask, jsonify
from extensions import db, limit_manager

app = Flask(__name__)

# Mock the verification to return user UID
def mock_verify_firebase_token():
    return {
        "uid": "cBylypg52cTDhf4NLfxeMEGxGzw1", # harshsharma6149@gmail.com
        "email": "harshsharma6149@gmail.com",
        "name": "Harsh Vardhan"
    }

import routes.billing_routes as br
# Override verify_firebase_token in billing_routes module
br.verify_firebase_token = mock_verify_firebase_token

with app.test_request_context():
    res = br.billing_config()
    print("Response data:")
    print(res.get_data(as_text=True))
