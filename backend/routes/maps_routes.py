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


@maps_bp.route('/maps/save', methods=['POST'])
def maps_save():
    """Persist a map card's resolved results (places + precise location) so the
    chat reopens with the exact same map — no second location popup. Keyed by
    the map_id the runner generated."""
    from extensions import db
    if not db:
        return jsonify({"ok": False}), 200
    body = request.get_json(silent=True) or {}
    map_id = (body.get('map_id') or '').strip()
    if not map_id:
        return jsonify({"ok": False, "error": "map_id required"}), 400
    places = body.get('places') or []
    if isinstance(places, list):
        places = places[:30]  # bound Firestore doc size
    # Route geometry can be thousands of points — downsample to stay well under
    # the 1MB Firestore doc limit while keeping the line smooth.
    route = body.get('route')
    if isinstance(route, dict) and isinstance(route.get('coordinates'), list):
        coords = route['coordinates']
        if len(coords) > 800:
            step = (len(coords) // 800) + 1
            route = {**route, 'coordinates': coords[::step]}
    doc = {
        "keyword": body.get('keyword'),
        "center": body.get('center'),
        "userLocation": body.get('userLocation'),
        "places": places,
        "source": body.get('source'),
        # route-planner fields
        "mode": body.get('mode'),
        "origin": body.get('origin'),
        "destination": body.get('destination'),
        "route": route,
    }
    doc = {k: v for k, v in doc.items() if v is not None}
    try:
        db.collection('map_results').document(map_id).set(doc)
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[Maps] save failed: {e}")
        return jsonify({"ok": False}), 200


@maps_bp.route('/maps/result/<map_id>', methods=['GET'])
def maps_result(map_id):
    """Return previously-saved results for a map card, or {found:false}."""
    from extensions import db
    if not db:
        return jsonify({"found": False}), 200
    try:
        snap = db.collection('map_results').document(map_id).get()
        if snap.exists:
            d = snap.to_dict() or {}
            d["found"] = True
            return jsonify(d)
    except Exception as e:
        print(f"[Maps] result fetch failed: {e}")
    return jsonify({"found": False}), 200


@maps_bp.route('/maps/route', methods=['GET'])
def maps_route():
    """Plan a journey between two places (geocode both ends + driving route).

    Origin can be the user's live location (from_lat/from_lng) or a place name
    (origin=). Destination is a place name. Returns both endpoints + the route
    geometry/distance/ETA so the map card can draw the whole journey."""
    dest_text = (request.args.get('destination') or '').strip()
    origin_text = (request.args.get('origin') or '').strip()
    fl = _f(request.args.get('from_lat'))
    fg = _f(request.args.get('from_lng'))

    # Resolve origin: live coords win; else geocode the origin text.
    if fl is not None and fg is not None:
        origin = {"lat": fl, "lng": fg, "label": "Your location"}
    elif origin_text:
        origin = maps_service.geocode(origin_text)
        if not origin:
            return jsonify({"error": "origin_not_found", "message": f"Couldn't find '{origin_text}'."}), 200
    else:
        return jsonify({"error": "no_origin", "message": "Need a start point (your location or a place name)."}), 200

    if not dest_text:
        return jsonify({"error": "no_destination", "message": "Need a destination."}), 200
    destination = maps_service.geocode(dest_text)
    if not destination:
        return jsonify({"error": "destination_not_found", "message": f"Couldn't find '{dest_text}'."}), 200

    route = maps_service.directions(origin["lat"], origin["lng"], destination["lat"], destination["lng"])
    return jsonify({
        "origin": origin,
        "destination": destination,
        "route": route or None,
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
