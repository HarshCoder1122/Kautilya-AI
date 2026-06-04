"""
Kautilya AI — Maps Service (Mappls / MapmyIndia, with OpenStreetMap fallback)

Powers the in-chat map card: nearby-place search, geocoding, and routing.

Design goal: ALWAYS return usable data so the map never looks broken.
  • Primary  : Mappls REST APIs (India-grade POIs, addresses, routing).
               Needs MAPPLS_CLIENT_ID / MAPPLS_CLIENT_SECRET (OAuth) and, for
               routing, MAPPLS_REST_KEY.
  • Fallback : free OpenStreetMap services (Overpass / Nominatim / OSRM) when
               Mappls credentials are missing or a call fails.

Every public function returns a plain dict/list of normalized shapes — the
route layer and frontend never see provider-specific formats.

Normalized place:
  {name, address, lat, lng, distance (m, optional), category (optional),
   eloc (optional)}
"""
import time
import threading

import requests

from config import (
    MAPPLS_CLIENT_ID, MAPPLS_CLIENT_SECRET, MAPPLS_REST_KEY, MAPPLS_MAP_SDK_KEY,
)

# Short, sane timeouts so a slow upstream never hangs the chat. (connect, read)
_HTTP_TIMEOUT = (4, 12)
_UA = "KautilyaAI/1.0 (+https://ai.revealiq.in)"  # Nominatim requires a UA

# ── Mappls OAuth token cache ─────────────────────────────────────────────
_token_lock = threading.Lock()
_token_cache = {"value": None, "expires_at": 0.0}


# ── Startup diagnostic ────────────────────────────────────────────────────
print(f"[Maps] Mappls credentials loaded: CLIENT_ID={'YES' if MAPPLS_CLIENT_ID else 'NO'} "
      f"CLIENT_SECRET={'YES' if MAPPLS_CLIENT_SECRET else 'NO'} "
      f"REST_KEY={'YES' if MAPPLS_REST_KEY else 'NO'} "
      f"MAP_SDK_KEY={'YES' if MAPPLS_MAP_SDK_KEY else 'NO'}")


def mappls_available() -> bool:
    return bool(MAPPLS_CLIENT_ID and MAPPLS_CLIENT_SECRET)


def map_sdk_key() -> str:
    """Public Map-SDK key the browser loads. Domain-locked, safe to expose."""
    return MAPPLS_MAP_SDK_KEY or ""


def _get_mappls_token():
    """Return a cached OAuth bearer token, refreshing ~2 min before expiry.
    Returns None if credentials are missing or the token call fails."""
    if not mappls_available():
        print("[Maps] Mappls NOT available (CLIENT_ID or CLIENT_SECRET missing)")
        return None
    now = time.time()
    if _token_cache["value"] and _token_cache["expires_at"] - 120 > now:
        return _token_cache["value"]
    with _token_lock:
        # Re-check inside the lock (another thread may have refreshed).
        if _token_cache["value"] and _token_cache["expires_at"] - 120 > time.time():
            return _token_cache["value"]
        try:
            print(f"[Maps] Requesting Mappls OAuth token (client_id={MAPPLS_CLIENT_ID[:8]}...)")
            r = requests.post(
                "https://outpost.mappls.com/api/security/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": MAPPLS_CLIENT_ID,
                    "client_secret": MAPPLS_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=_HTTP_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                tok = data.get("access_token")
                if tok:
                    _token_cache["value"] = tok
                    _token_cache["expires_at"] = time.time() + float(data.get("expires_in", 86400))
                    print(f"[Maps] Mappls OAuth token obtained OK (expires_in={data.get('expires_in')})")
                    return tok
                print(f"[Maps] Mappls token 200 but no access_token in response: {str(data)[:200]}")
            else:
                print(f"[Maps] Mappls token error {r.status_code}: {r.text[:300]}")
        except Exception as e:
            print(f"[Maps] Mappls token exception: {e}")
    return None


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── IP geolocation (fallback when the browser denies precise location) ────
def ip_location(ip: str):
    """Approximate {lat, lng, label} from an IP via ip-api. None on failure /
    local IPs."""
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


# ── Nearby search ─────────────────────────────────────────────────────────
def nearby(lat: float, lng: float, keyword: str, radius: int = 10000, limit: int = 20):
    """Nearby POIs for `keyword` around (lat,lng). Uses robust OSM Overpass search.
    Returns {"places": [...], "source": "osm"}."""
    keyword = (keyword or "restaurant").strip() or "restaurant"
    # Default to 10km radius so we don't miss places that are a bit far
    radius = max(250, min(int(radius or 10000), 50000))
    normalized_kw = _mappls_normalize_keyword(keyword)

    places = _osm_nearby(lat, lng, normalized_kw, radius, limit)
    return {"places": places, "source": "osm"}


def _mappls_normalize_keyword(keyword: str) -> str:
    kw = (keyword or "").strip().lower()
    # Normalize common variations to standard Mappls generic keywords
    if "restaurant" in kw or "dinner" in kw or "lunch" in kw or "eat" in kw or "khana" in kw or "food" in kw:
        return "restaurant"
    if "coffee" in kw or "cafe" in kw:
        return "cafe"
    if "pub" in kw or "bar" in kw:
        return "bar"
    if "hotel" in kw or "stay" in kw:
        return "hotel"
    if "atm" in kw:
        return "atm"
    if "bank" in kw:
        # Mappls prefers "bank" or "atm"
        return "bank"
    if "hospital" in kw or "clinic" in kw or "doctor" in kw:
        return "hospital"
    if "pharmacy" in kw or "chemist" in kw or "medicine" in kw or "medical" in kw:
        return "pharmacy"
    if "petrol" in kw or "fuel" in kw or "gas" in kw or "cng" in kw:
        return "fuel"
    if "school" in kw or "college" in kw or "university" in kw:
        return "school"
    if "park" in kw:
        return "park"
    if "gym" in kw or "fitness" in kw:
        return "gym"
    if "supermarket" in kw or "grocery" in kw or "kirana" in kw or "shop" in kw:
        return "supermarket"
    if "mall" in kw or "shopping" in kw:
        return "mall"
    if "salon" in kw or "saloon" in kw or "parlour" in kw or "hair" in kw:
        return "salon"
    return keyword


def _mappls_nearby(lat, lng, keyword, radius, limit):
    tok = _get_mappls_token()
    if not tok:
        print(f"[Maps] Mappls nearby skipped — no token (keyword={keyword})")
        return []
    normalized_kw = _mappls_normalize_keyword(keyword)
    print(f"[Maps] Mappls nearby: keyword='{keyword}' -> normalized='{normalized_kw}' loc={lat},{lng} r={radius}")
    try:
        r = requests.get(
            "https://atlas.mappls.com/api/places/textsearch/json",
            params={
                "query": normalized_kw,
                "location": f"{lat},{lng}",
                "radius": radius,
                "page": 1,
            },
            headers={"Authorization": f"bearer {tok}"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code == 204:
            print(f"[Maps] Mappls textsearch 204 No Content for '{normalized_kw}'")
            return []
        if r.status_code != 200:
            print(f"[Maps] Mappls textsearch {r.status_code}: {r.text[:300]}")
            return []
        body = r.json()
        suggested = body.get("suggestedLocations") or []
        
        out = []
        # Process up to `limit` items
        for i, s in enumerate(suggested[:limit]):
            plat = _to_float(s.get("latitude")) or _to_float(s.get("lat")) or _to_float(s.get("entryLatitude")) or _to_float(s.get("pLatitude"))
            plng = _to_float(s.get("longitude")) or _to_float(s.get("lng")) or _to_float(s.get("entryLongitude")) or _to_float(s.get("pLongitude"))
            
            # If coordinates are missing, fetch them via eLoc API
            if plat is None or plng is None:
                eloc = s.get("eLoc")
                if eloc:
                    try:
                        er = requests.get(
                            f"https://explore.mappls.com/apis/O2O/entity/{eloc}",
                            headers={"Authorization": f"bearer {tok}"},
                            timeout=2
                        )
                        if er.status_code == 200:
                            edata = er.json()
                            plat = _to_float(edata.get("latitude")) or _to_float(edata.get("lat")) or _to_float(edata.get("entryLatitude"))
                            plng = _to_float(edata.get("longitude")) or _to_float(edata.get("lng")) or _to_float(edata.get("entryLongitude"))
                    except Exception:
                        pass

            if plat is None or plng is None:
                if i == 0:
                    print(f"[Maps] Mappls item missing coordinates even after eLoc. Keys: {list(s.keys())}")
                continue
                
            out.append({
                "name": s.get("placeName") or "Unnamed place",
                "address": s.get("placeAddress") or "",
                "lat": plat,
                "lng": plng,
                "distance": _to_float(s.get("distance")),
                "category": s.get("type") or "",
                "eloc": s.get("eLoc") or "",
            })
            
        print(f"[Maps] Mappls nearby returned {len(out)} valid places for '{normalized_kw}'")
        return out
    except Exception as e:
        print(f"[Maps] Mappls nearby exception: {e}")
        return []


# keyword → (osm_key, osm_value) for the common asks; anything else falls back
# to a fuzzy name match in Overpass.
_OSM_TAGS = {
    "restaurant": ("amenity", "restaurant"), "food": ("amenity", "restaurant"),
    "eat": ("amenity", "restaurant"), "dinner": ("amenity", "restaurant"),
    "lunch": ("amenity", "restaurant"), "khana": ("amenity", "restaurant"),
    "cafe": ("amenity", "cafe"), "coffee": ("amenity", "cafe"),
    "bar": ("amenity", "bar"), "pub": ("amenity", "pub"),
    "hotel": ("tourism", "hotel"), "stay": ("tourism", "hotel"),
    "atm": ("amenity", "atm"), "bank": ("amenity", "bank"),
    "hospital": ("amenity", "hospital"), "clinic": ("amenity", "clinic"),
    "pharmacy": ("amenity", "pharmacy"), "medical": ("amenity", "pharmacy"),
    "chemist": ("amenity", "pharmacy"), "medicine": ("amenity", "pharmacy"),
    "fuel": ("amenity", "fuel"), "petrol": ("amenity", "fuel"),
    "gas": ("amenity", "fuel"), "cng": ("amenity", "fuel"),
    "school": ("amenity", "school"), "college": ("amenity", "college"),
    "park": ("leisure", "park"), "gym": ("leisure", "fitness_centre"),
    "supermarket": ("shop", "supermarket"), "grocery": ("shop", "supermarket"),
    "kirana": ("shop", "supermarket"), "mall": ("shop", "mall"),
    "salon": ("shop", "hairdresser"), "saloon": ("shop", "hairdresser"),
}


def _osm_tag_for(keyword):
    kw = keyword.lower()
    for token, tag in _OSM_TAGS.items():
        if token in kw:
            return tag
    return None


def _osm_nearby(lat, lng, keyword, radius, limit):
    tag = _osm_tag_for(keyword)
    safe_kw = keyword.replace('"', "").replace("\\", "")
    
    union_parts = []
    if tag:
        k, v = tag
        union_parts.append(f'node["{k}"="{v}"](around:{radius},{lat},{lng});')
        union_parts.append(f'way["{k}"="{v}"](around:{radius},{lat},{lng});')
    
    # Fuzzy name match is very slow over 10km if unchecked.
    # Restrict to nodes/ways that have AT LEAST a 'shop', 'building', or 'amenity' tag to use the index!
    for key in ["shop", "building", "amenity", "leisure", "tourism"]:
        union_parts.append(f'node["{key}"]["name"~"{safe_kw}",i](around:{radius},{lat},{lng});')
        union_parts.append(f'way["{key}"]["name"~"{safe_kw}",i](around:{radius},{lat},{lng});')
    
    query = (
        f"[out:json][timeout:25];"
        f"({''.join(union_parts)});"
        f"out center {limit * 3};"
    )
    for endpoint in ("https://overpass-api.de/api/interpreter",
                     "https://overpass.kumi.systems/api/interpreter"):
        try:
            r = requests.post(endpoint, data={"data": query}, timeout=(4, 20),
                              headers={"User-Agent": _UA})
            if r.status_code != 200:
                continue
            elements = r.json().get("elements", [])
            out = []
            for el in elements:
                tags = el.get("tags", {}) or {}
                name = tags.get("name")
                if not name:
                    continue
                plat = el.get("lat") or (el.get("center") or {}).get("lat")
                plng = el.get("lon") or (el.get("center") or {}).get("lon")
                plat, plng = _to_float(plat), _to_float(plng)
                if plat is None or plng is None:
                    continue
                addr = ", ".join(filter(None, [
                    tags.get("addr:street"), tags.get("addr:suburb"),
                    tags.get("addr:city"),
                ]))
                out.append({
                    "name": name,
                    "address": addr,
                    "lat": plat,
                    "lng": plng,
                    "distance": _haversine_m(lat, lng, plat, plng),
                    "category": tags.get("amenity") or tags.get("shop") or tags.get("tourism") or "",
                    "eloc": "",
                })
            out.sort(key=lambda p: p.get("distance") or 1e9)
            return out[:limit]
        except Exception as e:
            print(f"[Maps] Overpass exception ({endpoint}): {e}")
            continue
    return []


def _haversine_m(lat1, lng1, lat2, lng2):
    import math
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * R * math.asin(min(1.0, math.sqrt(a))), 1)


# ── Geocoding (free-text place → coordinates) ─────────────────────────────
def geocode(text: str):
    """{lat, lng, label} for a place/area name. Uses Nominatim.
    None if nothing matches."""
    text = (text or "").strip()
    if not text:
        return None
    return _osm_geocode(text)


def _mappls_geocode(text):
    tok = _get_mappls_token()
    if not tok:
        return None
    try:
        r = requests.get(
            "https://atlas.mappls.com/api/places/geocode",
            params={"address": text, "itemCount": 1},
            headers={"Authorization": f"bearer {tok}"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        results = r.json().get("copResults") or r.json().get("results")
        if isinstance(results, dict):
            results = [results]
        if results:
            top = results[0]
            lat, lng = _to_float(top.get("latitude")), _to_float(top.get("longitude"))
            if lat is not None and lng is not None:
                return {"lat": lat, "lng": lng, "label": top.get("formattedAddress") or text}
    except Exception as e:
        print(f"[Maps] Mappls geocode exception: {e}")
    return None


def _osm_geocode(text):
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


# ── Directions (route geometry for the "show route" tap) ──────────────────
def directions(from_lat, from_lng, to_lat, to_lng):
    """Driving route between two points. Uses OSRM.
    Returns {coordinates: [[lat,lng], ...], distance_m, duration_s} or None.
    Coordinates are [lat,lng] (Leaflet/Mappls marker order) for the frontend."""
    return _osrm_directions(from_lat, from_lng, to_lat, to_lng)


def _coords_lnglat_to_latlng(coords):
    out = []
    for c in coords or []:
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            lng, lat = _to_float(c[0]), _to_float(c[1])
            if lat is not None and lng is not None:
                out.append([lat, lng])
    return out


def _mappls_directions(fl, fg, tl, tg):
    if not MAPPLS_REST_KEY:
        return None
    try:
        # Mappls Route Advanced (OSRM-shaped). Path order is lng,lat;lng,lat.
        url = (f"https://apis.mappls.com/advancedmaps/v1/{MAPPLS_REST_KEY}"
               f"/route_adv/driving/{fg},{fl};{tg},{tl}")
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
        print(f"[Maps] Mappls directions exception: {e}")
        return None


def _osrm_directions(fl, fg, tl, tg):
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{fg},{fl};{tg},{tl}"
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
