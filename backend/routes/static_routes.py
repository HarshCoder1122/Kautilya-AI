"""
Kautilya AI — Static & Analytics Routes Blueprint
Handles root routes, html views, and basic analytics endpoints.
"""
import os
import psutil
import time
import requests
from flask import Blueprint, jsonify, send_from_directory, request, Response

from config import STATIC_FOLDER
from services.auth_service import verify_firebase_token

static_bp = Blueprint('static_routes', __name__)


# ---- Firebase Auth handler reverse-proxy ----------------------------------
# When the React app uses authDomain=ai.revealiq.in, Firebase's Google OAuth
# popup hits https://ai.revealiq.in/__/auth/handler (plus /__/auth/iframe.js
# and /__/firebase/init.json). Those paths are normally served by Firebase
# Hosting — since our app lives on a Flask + HF Space stack instead, we
# transparently proxy them to jarvis-a6e18.firebaseapp.com so the OAuth flow
# works without moving DNS to Firebase Hosting.
_FIREBASE_HOST = "https://jarvis-a6e18.firebaseapp.com"
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-encoding",
    "content-length",
}

@static_bp.route('/__/<path:subpath>', methods=['GET', 'POST', 'OPTIONS'])
def firebase_auth_proxy(subpath):
    upstream_url = f"{_FIREBASE_HOST}/__/{subpath}"
    try:
        upstream = requests.request(
            method=request.method,
            url=upstream_url,
            params=request.args,
            data=request.get_data() if request.method != 'GET' else None,
            headers={k: v for k, v in request.headers.items()
                     if k.lower() != 'host'},
            cookies=request.cookies,
            allow_redirects=False,
            stream=True,
            timeout=(5, 30),
        )
    except Exception as e:
        return jsonify({"error": f"Auth proxy upstream failed: {e}"}), 502

    headers = [(k, v) for k, v in upstream.raw.headers.items()
               if k.lower() not in _HOP_BY_HOP]
    return Response(upstream.iter_content(chunk_size=8192),
                    status=upstream.status_code, headers=headers)


@static_bp.route('/')
@static_bp.route('/dashboard', defaults={'subpath': ''})
@static_bp.route('/dashboard/', defaults={'subpath': ''})
@static_bp.route('/dashboard/<path:subpath>')
@static_bp.route('/login')
def home(subpath=None):
    """Serve the React SPA with no-cache so browsers always load the latest
    index.html. Hashed JS/CSS filenames handle long-term asset caching."""
    from flask import make_response
    resp = make_response(send_from_directory(STATIC_FOLDER, 'index.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@static_bp.route('/favicon.ico')
def favicon():
    """Serve favicon, falling back to logo.png when favicon.ico is absent."""
    favicon_path = os.path.join(STATIC_FOLDER, 'favicon.ico')
    if os.path.exists(favicon_path):
        return send_from_directory(STATIC_FOLDER, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    return send_from_directory(STATIC_FOLDER, 'logo.png', mimetype='image/png')


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


@static_bp.route('/health', methods=['GET'])
def health_check():
    """Detailed health check endpoint for Render (JSON)."""
    from config import GROQ_API_KEYS
    return jsonify({
        "status": "healthy",
        "service": "KAUTILYA AI",
        "llm_groq": len(GROQ_API_KEYS) > 0,
    })


@static_bp.route('/analytics/trends', methods=['GET'])
def api_analytics_trends():
    """Return real sentiment and lead status trends for the dashboard."""
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    if not db: return jsonify({"trends": [], "sentiment_stats": {"positive": 0, "neutral": 0, "negative": 0}})

    try:
        # Get last 7 days of leads to build a trend
        from datetime import datetime, timedelta
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        leads_ref = db.collection('leads').where(
            filter=firestore.FieldFilter('uid', '==', uid)
        ).where(
            filter=firestore.FieldFilter('created_at', '>=', seven_days_ago)
        ).stream()
        
        daily_stats = {}
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        
        for doc in leads_ref:
            data = doc.to_dict()
            ts = data.get('created_at')
            if ts and hasattr(ts, 'strftime'):
                day_str = ts.strftime("%Y-%m-%d")
                status = data.get('status', 'new').lower()
                
                if day_str not in daily_stats:
                    daily_stats[day_str] = {"hot": 0, "warm": 0, "cold": 0}
                
                # Map status to dashboard categories
                if status in ('hot', 'qualified'): daily_stats[day_str]['hot'] += 1
                elif status in ('warm', 'new'): daily_stats[day_str]['warm'] += 1
                else: daily_stats[day_str]['cold'] += 1
                
                # Sentiment
                sent = data.get('sentiment', 'neutral').lower()
                if sent in sentiment_counts:
                    sentiment_counts[sent] += 1

        # Format trends for frontend
        trends = []
        for i in range(6, -1, -1):
            d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            stats = daily_stats.get(d, {"hot": 0, "warm": 0, "cold": 0})
            trends.append({"date": d, **stats})

        # Calculate percentages for sentiment
        total_sent = sum(sentiment_counts.values())
        if total_sent > 0:
            sentiment_stats = {k: round((v/total_sent)*100) for k, v in sentiment_counts.items()}
        else:
            sentiment_stats = {"positive": 0, "neutral": 0, "negative": 0}

        return jsonify({
            "trends": trends,
            "sentiment_stats": sentiment_stats
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
