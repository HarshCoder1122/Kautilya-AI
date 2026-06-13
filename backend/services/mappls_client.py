import os
import time
import requests

_HTTP_TIMEOUT = 10
_UA = "KautilyaAI/1.0 (+https://ai.revealiq.in)"

_TOKEN_CACHE = {
    "access_token": None,
    "expires_at": 0
}

def is_configured():
    return bool(os.environ.get("MAPPLS_CLIENT_ID") and os.environ.get("MAPPLS_CLIENT_SECRET"))

def _get_token():
    client_id = os.environ.get("MAPPLS_CLIENT_ID")
    client_secret = os.environ.get("MAPPLS_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    now = time.time()
    if _TOKEN_CACHE["access_token"] and now < _TOKEN_CACHE["expires_at"]:
        return _TOKEN_CACHE["access_token"]

    url = "https://outpost.mapmyindia.com/api/security/oauth/token"
    try:
        r = requests.post(url, data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }, timeout=_HTTP_TIMEOUT)
        
        if r.status_code == 200:
            data = r.json()
            _TOKEN_CACHE["access_token"] = data.get("access_token")
            expires_in = int(data.get("expires_in", 86400))
            _TOKEN_CACHE["expires_at"] = now + expires_in - 300
            return _TOKEN_CACHE["access_token"]
        else:
            print(f"[Mappls] Failed to get token: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[Mappls] Token exception: {e}")

    return None

def nearby(lat: float, lng: float, keyword: str, radius: int, limit: int = 20):
    token = _get_token()
    if not token:
        return None
    
    url = "https://atlas.mapmyindia.com/api/places/nearby/json"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}
    params = {
        "keywords": keyword,
        "refLocation": f"{lat},{lng}",
        "radius": radius
    }
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=_HTTP_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            locations = data.get("suggestedLocations") or []
            out = []
            for loc in locations:
                try:
                    out.append({
                        "name": loc.get("placeName"),
                        "address": loc.get("placeAddress"),
                        "lat": float(loc.get("latitude")),
                        "lng": float(loc.get("longitude")),
                        "distance": int(loc.get("distance", 0)),
                        "category": keyword
                    })
                except (TypeError, ValueError):
                    pass
            return out[:limit]
        else:
            print(f"[Mappls] Nearby error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[Mappls] Nearby exception: {e}")
        
    return None

def geocode(text: str):
    token = _get_token()
    if not token:
        return None
        
    url = "https://atlas.mapmyindia.com/api/places/geocode"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}
    params = {"address": text}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=_HTTP_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            results = data.get("copResults") or []
            if results:
                top = results[0]
                try:
                    return {
                        "lat": float(top.get("latitude")),
                        "lng": float(top.get("longitude")),
                        "label": top.get("formattedAddress") or text
                    }
                except (TypeError, ValueError):
                    pass
        else:
            print(f"[Mappls] Geocode error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[Mappls] Geocode exception: {e}")
        
    return None

def directions(from_lat, from_lng, to_lat, to_lng):
    rest_key = os.environ.get("MAPPLS_REST_KEY")
    if rest_key:
        url = f"https://apis.mapmyindia.com/advancedmaps/v1/{rest_key}/route_adv/driving/{from_lng},{from_lat};{to_lng},{to_lat}"
        headers = {"User-Agent": _UA}
    else:
        token = _get_token()
        if not token:
            return None
        url = f"https://apis.mapmyindia.com/advancedmaps/v1/route_adv/driving/{from_lng},{from_lat};{to_lng},{to_lat}"
        headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}
        
    params = {"geometries": "geojson", "overview": "full"}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=_HTTP_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            routes = data.get("routes") or []
            if not routes:
                return None
                
            rt = routes[0]
            coords = rt.get("geometry", {}).get("coordinates", [])
            
            out_coords = []
            for c in coords:
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    try:
                        out_coords.append([float(c[1]), float(c[0])])
                    except (TypeError, ValueError):
                        pass
                        
            return {
                "coordinates": out_coords,
                "distance_m": float(rt.get("distance", 0)),
                "duration_s": float(rt.get("duration", 0))
            }
        else:
            print(f"[Mappls] Directions error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[Mappls] Directions exception: {e}")
        
    return None
