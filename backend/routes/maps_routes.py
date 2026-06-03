"""
Kautilya AI — Maps Routes

Backs the in-chat Mappls map card:
  GET /api/maps/config      → { available, sdk_key }      (public SDK key)
  GET /api/maps/nearby      → { center, userLocation, places, source }
  GET /api/maps/directions  → { coordinates, distance_m, duration_s }

The frontend MapCard requests the browser's precise location (permission
popup) and passes lat/lng here. If the user denies it, we fall back to coarse
IP geolocation so the map still shows something useful.
"""
from flask import Blueprint, request, jsonify

from services import maps_service
from middleware.security import get_real_client_ip

maps_bp = Blueprint('maps', __name__)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@maps_bp.route('/maps/config', methods=['GET'])
def maps_config():
    return jsonify({
        "available": bool(maps_service.map_sdk_key()),
        "sdk_key": maps_service.map_sdk_key(),
        "provider": "mappls" if maps_service.mappls_available() else "osm",
    })


@maps_bp.route('/maps/nearby', methods=['GET'])
def maps_nearby():
    keyword = (request.args.get('keyword') or 'restaurant').strip()
    radius = request.args.get('radius', 3000)
    try:
        radius = int(radius)
    except (TypeError, ValueError):
        radius = 3000

    lat = _f(request.args.get('lat'))
    lng = _f(request.args.get('lng'))
    source = "gps"

    # No precise location from the browser → fall back to IP geolocation.
    if lat is None or lng is None:
        ip = get_real_client_ip(request)
        loc = maps_service.ip_location(ip)
        if not loc:
            return jsonify({
                "error": "no_location",
                "message": "Couldn't determine your location. Please allow location access and try again.",
            }), 200
        lat, lng, source = loc["lat"], loc["lng"], "ip"
        user_label = loc.get("label", "your area")
    else:
        user_label = "Your location"

    result = maps_service.nearby(lat, lng, keyword, radius=radius)
    return jsonify({
        "center": [lat, lng],
        "userLocation": {"lat": lat, "lng": lng, "label": user_label, "source": source},
        "keyword": keyword,
        "places": result["places"],
        "source": result["source"],
    })


@maps_bp.route('/maps/directions', methods=['GET'])
def maps_directions():
    fl = _f(request.args.get('from_lat'))
    fg = _f(request.args.get('from_lng'))
    tl = _f(request.args.get('to_lat'))
    tg = _f(request.args.get('to_lng'))
    if None in (fl, fg, tl, tg):
        return jsonify({"error": "from_lat, from_lng, to_lat, to_lng are required"}), 400
    route = maps_service.directions(fl, fg, tl, tg)
    if not route:
        return jsonify({"error": "no_route"}), 200
    return jsonify(route)
