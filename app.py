"""
Kautilya AI — Core Orchestrator (Thin app.py)
This is the entry point for the Flask application. It only handles configuration,
middleware initialization, blueprint registration, and global handlers.
"""
import os
import requests
import logging
from flask import Flask, jsonify, send_from_directory, Response, request
from flask_cors import CORS
from dotenv import load_dotenv

# Set up logging before local imports
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filename='jarvis.log')
logger = logging.getLogger(__name__)

load_dotenv()

# Extensions & Config
from config import STATIC_FOLDER
from extensions import db, limit_manager

# Blueprints
from routes.chat_routes import chat_bp
from routes.voice_routes import voice_bp
from routes.user_routes import user_bp
from routes.billing_routes import billing_bp
from routes.keys_routes import keys_bp
from routes.agents_routes import agents_bp
from routes.campaigns_routes import campaigns_bp
from routes.export_routes import export_bp
from routes.static_routes import static_bp

app = Flask(__name__, static_folder=STATIC_FOLDER)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

CORS(app, resources={r"/api/*": {"origins": "*"}})

# Register blueprints
app.register_blueprint(static_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(voice_bp)
app.register_blueprint(user_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(keys_bp)
app.register_blueprint(agents_bp)
app.register_blueprint(campaigns_bp)
app.register_blueprint(export_bp)

# Global Security Headers
@app.after_request
def set_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "https://www.gstatic.com https://apis.google.com "
            "https://checkout.razorpay.com https://cdn.razorpay.com; "
        "style-src 'self' 'unsafe-inline' "
            "https://fonts.googleapis.com https://cdnjs.cloudflare.com "
            "https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https: http: https://unpkg.com; "
        "connect-src 'self' https: wss: https://api.razorpay.com https://lumberjack.razorpay.com; "
        "media-src 'self' blob: https:; "
        "frame-src 'self' https://accounts.google.com https://*.firebaseapp.com "
            "https://api.razorpay.com https://lumberjack.razorpay.com https://checkout.razorpay.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers['Content-Security-Policy'] = csp
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = (
        'camera=(self), microphone=(self), geolocation=(self), '
        'payment=(self), usb=(), magnetometer=(self), gyroscope=(self), accelerometer=(self)'
    )
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled Exception: {str(e)}")
    return jsonify({
        "error": "Internal Server Error",
        "message": "KAUTILYA encountered an unexpected error but stayed online.",
        "status": 500
    }), 500

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(STATIC_FOLDER, 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory(STATIC_FOLDER, 'sw.js')

@app.route('/__/<path:firebase_path>')
def firebase_proxy(firebase_path):
    firebase_url = f"https://jarvis-a6e18.firebaseapp.com/__/{firebase_path}"
    params = request.query_string.decode()
    if params:
        firebase_url += f"?{params}"
    try:
        resp = requests.get(firebase_url, timeout=15)
        excluded_headers = {'content-encoding', 'transfer-encoding', 'connection'}
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        return Response(resp.content, status=resp.status_code, headers=headers)
    except Exception as e:
        logger.error(f"[Firebase Proxy] Error: {e}")
        return Response("Firebase proxy error", status=502)

if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=PORT)
