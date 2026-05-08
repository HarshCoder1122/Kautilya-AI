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
@static_bp.route('/dashboard', defaults={'subpath': ''})
@static_bp.route('/dashboard/', defaults={'subpath': ''})
@static_bp.route('/dashboard/<path:subpath>')
def home(subpath=None):
    """Serve the main React SPA.
    Both the root (/) and /dashboard routes serve the same index.html.
    React Router handles the client-side navigation.
    """
    return send_from_directory(STATIC_FOLDER, 'index.html')


@static_bp.route('/playground')
def serve_playground():
    """Serve the developer playground page."""
    return send_from_directory(STATIC_FOLDER, 'playground.html')


@static_bp.route('/docs')
def serve_docs():
    """Serve the developer docs page (with Copy-for-AI button)."""
    return send_from_directory(STATIC_FOLDER, 'docs.html')


@static_bp.route('/embed.html')
def serve_embed_html():
    """Serve the web widget embed container."""
    return send_from_directory(STATIC_FOLDER, 'embed.html')


@static_bp.route('/embed.js')
def serve_embed_js():
    """Serve the web widget loader script."""
    return send_from_directory(STATIC_FOLDER, 'embed.js')


@static_bp.route('/PROJECT_DOCUMENTATION.md')
def serve_docs_md():
    """Serve the raw markdown so the /docs page can render it."""
    from config import BASE_DIR
    return send_from_directory(BASE_DIR, 'PROJECT_DOCUMENTATION.md', mimetype='text/markdown')


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
