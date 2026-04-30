"""
Kautilya AI — Static & Analytics Routes Blueprint
Handles root routes, html views, and basic analytics endpoints.
"""
import os
import psutil
import time
from flask import Blueprint, jsonify, send_from_directory, request

from config import STATIC_FOLDER
from services.auth_service import verify_firebase_token

static_bp = Blueprint('static_routes', __name__)


@static_bp.route('/')
def home():
    """Serve the main chat application."""
    return send_from_directory(STATIC_FOLDER, 'index.html')


@static_bp.route('/coder')
def serve_coder_auth():
    """Serve the CLI authentication bridge page."""
    return send_from_directory(STATIC_FOLDER, 'coder_auth.html')


@static_bp.route('/dashboard-legacy')
def serve_dashboard_legacy():
    """Legacy single-file dashboard. Kept available during the v2 rollout."""
    return send_from_directory(STATIC_FOLDER, 'dashboard.html')


@static_bp.route('/dashboard', defaults={'subpath': ''})
@static_bp.route('/dashboard/', defaults={'subpath': ''})
@static_bp.route('/dashboard/<path:subpath>')
def serve_dashboard(subpath):
    """Serve the Vue 3 SPA. We do SPA history-fallback: any /dashboard/...
    URL returns the same index.html so Vue Router can resolve client-side.

    Build artifacts live in `static/dashboard-v2/` (run `npm run build` inside
    `dashboard-app/`). If the SPA hasn't been built yet, we transparently
    fall back to the legacy single-file dashboard so the app stays usable.
    """
    spa_dir = os.path.join(STATIC_FOLDER, 'dashboard-v2')
    spa_index = os.path.join(spa_dir, 'index.html')
    if os.path.exists(spa_index):
        return send_from_directory(spa_dir, 'index.html')
    # SPA not built yet — fall back to legacy
    return send_from_directory(STATIC_FOLDER, 'dashboard.html')


@static_bp.route('/playground')
def serve_playground():
    """Serve the developer playground page."""
    return send_from_directory(STATIC_FOLDER, 'playground.html')


@static_bp.route('/favicon.ico')
def favicon():
    """Serve favicon."""
    return send_from_directory(STATIC_FOLDER, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@static_bp.route('/system/status', methods=['GET'])
def system_status():
    """Basic unauthenticated system status metrics."""
    try:
        import platform
        return jsonify({
            "status": "online",
            "cpu_percent": psutil.cpu_percent(),
            "ram": {"percent": psutil.virtual_memory().percent},
            "platform": platform.system(),
            "uptime": int(time.time() - psutil.boot_time())
        })
    except Exception as e:
        return jsonify({"cpu_percent": 0, "ram": {"percent": 0}, "error": str(e)})


@static_bp.route('/health')
def health_check_simple():
    """Health check endpoint for Render (text)."""
    return "OK", 200


@static_bp.route('/api/health', methods=['GET'])
def health_check():
    """Detailed health check endpoint for Render (JSON)."""
    from config import GROQ_API_KEYS
    return jsonify({
        "status": "healthy",
        "service": "KAUTILYA AI",
        "llm_groq": len(GROQ_API_KEYS) > 0,
    })


@static_bp.route('/api/analytics/trends', methods=['GET'])
def api_analytics_trends():
    """Return sentiment and conversion trends for the dashboard."""
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    
    # Generic placeholder logic - aggregation would be done here
    return jsonify({
        "trends": [
            {"date": "2024-04-01", "hot": 5, "warm": 12, "cold": 8},
            {"date": "2024-04-02", "hot": 8, "warm": 10, "cold": 5},
            {"date": "2024-04-03", "hot": 12, "warm": 15, "cold": 10}
        ],
        "sentiment_stats": {"positive": 65, "neutral": 20, "negative": 15}
    })
