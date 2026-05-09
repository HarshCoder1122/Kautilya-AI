"""
Kautilya AI — Core Orchestrator (Thin app.py)
This is the entry point for the Flask application.
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

# Import Blueprints
from routes.chat_routes import chat_bp
from routes.voice_routes import voice_bp
from routes.user_routes import user_bp
from routes.billing_routes import billing_bp
from routes.keys_routes import keys_bp
from routes.agents_routes import agents_bp
from routes.campaigns_routes import campaigns_bp
from routes.export_routes import export_bp
from routes.static_routes import static_bp
from routes.telephony_routes import telephony_bp
from routes.webhooks_routes import webhooks_bp
from routes.openai_compat_routes import openai_compat_bp
from routes.background_routes import background_bp
from routes.code_routes import code_bp
from routes.research_routes import research_bp
from routes.integrations_routes import integrations_bp
from routes.embed_routes import embed_bp
from routes.artifact_routes import artifact_bp
from routes.tts_routes import tts_bp

app = Flask(__name__, static_folder=STATIC_FOLDER)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

# Optional Gzip Compression for Performance
try:
    from flask_compress import Compress
    Compress(app)
    logger.info("[App] Gzip compression enabled via flask-compress")
except ImportError:
    logger.warning("[App] flask-compress not found, skipping Gzip compression")

CORS(app, resources={r"/api/*": {"origins": "*"}})

# Register blueprints
app.register_blueprint(static_bp)
app.register_blueprint(chat_bp, url_prefix='/api')
app.register_blueprint(voice_bp, url_prefix='/api')
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(billing_bp, url_prefix='/api')
app.register_blueprint(keys_bp, url_prefix='/api')
app.register_blueprint(agents_bp, url_prefix='/api')
app.register_blueprint(campaigns_bp, url_prefix='/api')
app.register_blueprint(telephony_bp, url_prefix='/api')
app.register_blueprint(webhooks_bp, url_prefix='/api')
app.register_blueprint(openai_compat_bp) # v1 prefix handled inside
app.register_blueprint(background_bp, url_prefix='/api')
app.register_blueprint(code_bp, url_prefix='/api')
app.register_blueprint(research_bp, url_prefix='/api')
app.register_blueprint(integrations_bp, url_prefix='/api')
app.register_blueprint(embed_bp, url_prefix='/api')
app.register_blueprint(artifact_bp, url_prefix='/api')
app.register_blueprint(tts_bp, url_prefix='/api')

# CORS for special endpoints
CORS(app, resources={r"/v1/*": {"origins": "*"}})
CORS(app, resources={r"/embed/*": {"origins": "*"}, r"/embed.js": {"origins": "*"}})

# Global Security & Cache Headers
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
            "https://cdn.jsdelivr.net https://api.fontshare.com; "
        "font-src 'self' data: https://fonts.gstatic.com https://fonts.googleapis.com https://api.fontshare.com; "
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
    
    # Smart Caching for Production Performance
    path = request.path
    if path == '/' or path.endswith('index.html'):
        # THE CRITICAL FIX: Ensure index.html is NEVER cached so users always get fresh build references
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    elif any(path.endswith(ext) for ext in ['.js', '.css', '.woff2', '.png', '.jpg', '.jpeg', '.svg', '.ico']):
        # Static assets with hashes should be cached long-term
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        # Remove contradictory headers for assets
        response.headers.pop('Pragma', None)
        response.headers.pop('Expires', None)
    else:
        # Default for API and other routes: no-store
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    logger.error(f"Unhandled Exception: {str(e)}")
    return jsonify({
        "error": "Internal Server Error",
        "message": "KAUTILYA encountered an unexpected error but stayed online.",
        "status": 500
    }), 500

@app.route('/api/config/firebase', methods=['GET'])
def get_firebase_config():
    from extensions import FIREBASE_AVAILABLE
    if not FIREBASE_AVAILABLE:
        return jsonify({"error": "Firebase Admin not initialized"}), 503
    
    # Env priority
    env_config = {
        "apiKey": os.environ.get("FIREBASE_API_KEY"),
        "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.environ.get("FIREBASE_PROJECT_ID", "jarvis-a6e18"),
        "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.environ.get("FIREBASE_APP_ID")
    }
    if env_config["apiKey"] and env_config["appId"]:
        return jsonify(env_config)

    # Dynamic fetch
    try:
        from firebase_admin import project_management
        apps = project_management.list_web_apps()
        if apps:
            config = apps[0].get_config()
            return jsonify({
                "apiKey": config.api_key,
                "authDomain": f"{config.project_id}.firebaseapp.com",
                "projectId": config.project_id,
                "storageBucket": f"{config.project_id}.appspot.com",
                "messagingSenderId": config.messaging_sender_id,
                "appId": config.app_id
            })
    except Exception as e:
        logger.warning(f"Config dynamic fetch failed: {e}")
    
    return jsonify({
        "apiKey": env_config["apiKey"] or "",
        "authDomain": env_config["authDomain"] or "jarvis-a6e18.firebaseapp.com",
        "projectId": "jarvis-a6e18",
        "storageBucket": "jarvis-a6e18.appspot.com",
        "messagingSenderId": env_config["messagingSenderId"] or "",
        "appId": env_config["appId"] or ""
    })

@app.route('/__/<path:firebase_path>')
def firebase_proxy(firebase_path):
    firebase_url = f"https://jarvis-a6e18.firebaseapp.com/__/{firebase_path}"
    try:
        resp = requests.get(firebase_url, timeout=15)
        excluded_headers = {'content-encoding', 'transfer-encoding', 'connection'}
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        return Response(resp.content, status=resp.status_code, headers=headers)
    except Exception as e:
        return Response(f"Proxy error: {e}", status=502)

# SPA Catch-all (Must be last)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # If the path actually exists as a file in STATIC_FOLDER, serve it
    if path and os.path.exists(os.path.join(STATIC_FOLDER, path)):
        return send_from_directory(STATIC_FOLDER, path)
    
    # Exclude API and system routes from catch-all
    if path.startswith(('api/', 'v1/', 'embed', 'static/')):
        return jsonify({"error": "Not Found", "path": path}), 404
        
    # Default to SPA index
    return send_from_directory(STATIC_FOLDER, 'index.html')

if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=PORT)
