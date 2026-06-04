"""
Kautilya AI — Maps Service (OpenStreetMap)

Powers the in-chat map card: nearby-place search, geocoding, and routing.
Uses free OpenStreetMap services (Nominatim / OSRM).
"""
import requests
import math

_HTTP_TIMEOUT = (4, 12)
_UA = "KautilyaAI/1.0 (+https://ai.revealiq.in)"


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ip_location(ip: str):
    """Approximate {lat, lng, label} from an IP via ip-api. None on failure / local IPs."""
    if not ip or ip in ("127.0.0.1", "localhost", "::1", "unknown"):
        return None
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=(3, 5))
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "success":
                lat, lng = _to_float(d.get("lat")), _to_float(d.get("lon"))
                if lat is not None and lng is not None:
                    label = ", ".join([p for p in (d.get("city"), d.get("regionName")) if p])
                    return {"lat": lat, "lng": lng, "label": label or "your area"}
    except Exception as e:
        print(f"[Maps] ip_location failed: {e}")
    return None


def nearby(lat: float, lng: float, keyword: str, radius: int = 10000, limit: int = 20):
    """Nearby POIs for `keyword` around (lat,lng).
    Returns {"places": [...], "source": "osm"}."""
    keyword = (keyword or "restaurant").strip() or "restaurant"
    radius = max(250, min(int(radius or 10000), 50000))

    places = _osm_nearby(lat, lng, keyword, radius, limit)
    return {"places": places, "source": "osm"}


def _osm_nearby(lat, lng, keyword, radius, limit):
    # Use Nominatim for arbitrary text search (avoids Overpass timeout issues)
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": keyword, "format": "json", "limit": limit, "lat": lat, "lon": lng},
            headers={"User-Agent": _UA},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code == 200:
            arr = r.json()
            if not arr:
                return [{"name": "Debug Empty", "address": f"Nominatim returned empty list. Query: {keyword}", "lat": lat, "lng": lng, "distance": 0, "category": "error"}]
            out = []
            for top in arr:
                plat, plng = _to_float(top.get("lat")), _to_float(top.get("lon"))
                if plat is not None and plng is not None:
                    dist = _haversine_m(lat, lng, plat, plng)
                    out.append({
                        "name": top.get("name") or top.get("display_name", "").split(",")[0],
                        "address": top.get("display_name"),
                        "lat": plat,
                        "lng": plng,
                        "distance": round(dist),
                        "category": top.get("class") or ""
                    })
            out.sort(key=lambda x: x["distance"])
            print(f"[Maps] OSM nearby returned {len(out)} places for '{keyword}' via Nominatim")
            return out[:limit]
        else:
            return [{"name": f"Error: {r.status_code}", "address": r.text[:100], "lat": lat, "lng": lng, "distance": 0, "category": "error"}]
    except Exception as e:
        print(f"[Maps] Nominatim nearby exception: {e}")
        return [{"name": "Exception", "address": str(e), "lat": lat, "lng": lng, "distance": 0, "category": "error"}]


def _haversine_m(lat1, lng1, lat2, lng2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * R * math.asin(min(1.0, math.sqrt(a))), 1)


def geocode(text: str):
    """{lat, lng, label} for a place/area name. Uses Nominatim."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": text, "format": "json", "limit": 1, "countrycodes": "in"},
            headers={"User-Agent": _UA},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code == 200:
            arr = r.json()
            if arr:
                top = arr[0]
                lat, lng = _to_float(top.get("lat")), _to_float(top.get("lon"))
                if lat is not None and lng is not None:
                    return {"lat": lat, "lng": lng, "label": top.get("display_name") or text}
    except Exception as e:
        print(f"[Maps] Nominatim geocode exception: {e}")
    return None


def directions(from_lat, from_lng, to_lat, to_lng):
    """Driving route between two points. Uses OSRM.
    Returns {coordinates: [[lat,lng], ...], distance_m, duration_s} or None."""
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{from_lng},{from_lat};{to_lng},{to_lat}"
        r = requests.get(url, params={"geometries": "geojson", "overview": "full"},
                         timeout=_HTTP_TIMEOUT)
        if r.status_code != 200:
            return None
        routes = r.json().get("routes") or []
        if not routes:
            return None
        rt = routes[0]
        coords = _coords_lnglat_to_latlng((rt.get("geometry") or {}).get("coordinates"))
        if not coords:
            return None
        return {"coordinates": coords,
                "distance_m": _to_float(rt.get("distance")),
                "duration_s": _to_float(rt.get("duration"))}
    except Exception as e:
        print(f"[Maps] OSRM directions exception: {e}")
        return None


def _coords_lnglat_to_latlng(coords):
    out = []
    for c in coords or []:
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            lng, lat = _to_float(c[0]), _to_float(c[1])
            if lat is not None and lng is not None:
                out.append([lat, lng])
    return out
