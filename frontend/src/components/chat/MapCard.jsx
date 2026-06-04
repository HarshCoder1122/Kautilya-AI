/**
 * In-chat interactive map card.
 *
 * Flow when the model emits [MAP_SEARCH: <keyword>]:
 *   1. Ask the browser for the user's PRECISE location (permission popup).
 *   2. Call /api/maps/nearby (Mappls-powered, OSM fallback) with those coords
 *      — or, if the user denies, the backend falls back to IP geolocation.
 *   3. Render a Leaflet map (loaded from cdnjs — the only map lib allowed by
 *      our CSP) with a "you are here" marker + numbered place markers, and a
 *      tappable list. Tapping a place draws the driving route.
 *
 * Leaflet is used for rendering because apis.mappls.com is not in our CSP
 * script-src (so the Mappls JS SDK can't load in-browser); the India-quality
 * search + routing still comes from Mappls via the backend.
 */
import { useEffect, useRef, useState } from "react";
import { MapPin, NavigationArrow, Spinner, MapTrifold } from "@phosphor-icons/react";
import { mapsAPI } from "../../lib/api";

const LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js";
const LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css";

let _leafletPromise = null;
export function loadLeaflet() {
  if (typeof window !== "undefined" && window.L) return Promise.resolve(window.L);
  if (_leafletPromise) return _leafletPromise;
  _leafletPromise = new Promise((resolve, reject) => {
    try {
      if (!document.querySelector("link[data-leaflet]")) {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = LEAFLET_CSS;
        link.setAttribute("data-leaflet", "1");
        document.head.appendChild(link);
      }
      const existing = document.querySelector("script[data-leaflet]");
      if (existing) {
        existing.addEventListener("load", () => resolve(window.L));
        existing.addEventListener("error", reject);
        if (window.L) resolve(window.L);
        return;
      }
      const s = document.createElement("script");
      s.src = LEAFLET_JS;
      s.async = true;
      s.setAttribute("data-leaflet", "1");
      s.onload = () => resolve(window.L);
      s.onerror = () => reject(new Error("leaflet load failed"));
      document.body.appendChild(s);
    } catch (e) {
      reject(e);
    }
  });
  return _leafletPromise;
}

export function fmtDist(m) {
  if (m == null || isNaN(m)) return "";
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

export function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function userPinHtml() {
  return `<div style="width:18px;height:18px;border-radius:50%;background:#2563eb;border:3px solid #fff;box-shadow:0 0 0 2px rgba(37,99,235,.45);"></div>`;
}

function placePinHtml(n) {
  return `<div style="position:relative;width:26px;height:34px;">
    <svg width="26" height="34" viewBox="0 0 26 34" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M13 0C5.82 0 0 5.82 0 13c0 9.25 13 21 13 21s13-11.75 13-21C26 5.82 20.18 0 13 0z" fill="#e11d48"/>
      <circle cx="13" cy="13" r="9" fill="#fff"/>
    </svg>
    <span style="position:absolute;top:3px;left:0;width:26px;text-align:center;font:700 12px system-ui;color:#e11d48;">${n}</span>
  </div>`;
}

function placePopupHtml(p) {
  const dist = fmtDist(p.distance);
  const dir = `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}`;
  return `<div style="min-width:160px;font:13px system-ui;line-height:1.35;">
    <div style="font-weight:700;margin-bottom:2px;">${escapeHtml(p.name)}</div>
    ${p.address ? `<div style="color:#666;font-size:11px;margin-bottom:4px;">${escapeHtml(p.address)}</div>` : ""}
    ${dist ? `<div style="color:#e11d48;font-size:11px;font-weight:600;margin-bottom:4px;">${dist} away</div>` : ""}
    <a href="${dir}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;font-size:12px;font-weight:600;">Directions &#8599;</a>
  </div>`;
}

export function MapCard({ keyword = "places", radius = 3000, map_id }) {
  const mapElRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const routeRef = useRef(null);
  const LRef = useRef(null);
  const userRef = useRef(null); // {lat,lng,label,source}

  const [status, setStatus] = useState("locating"); // locating | loading | ready | error
  const [places, setPlaces] = useState([]);
  const [errMsg, setErrMsg] = useState("");
  const [activeIdx, setActiveIdx] = useState(-1);
  const [source, setSource] = useState("");

  // Step 1 — restore saved results if this chat was reopened (no popup);
  // otherwise ask for precise location (permission popup) and fetch nearby,
  // then persist the result so the next reopen restores it verbatim.
  useEffect(() => {
    let cancelled = false;

    const persist = (data) => {
      if (!map_id || !data || !data.userLocation || !Array.isArray(data.places) || !data.places.length) return;
      mapsAPI.saveResult({
        map_id, keyword,
        center: data.center,
        userLocation: data.userLocation,
        places: data.places,
        source: data.source,
      }).catch(() => {});
    };

    const fetchNearby = async (lat, lng) => {
      try {
        setStatus("loading");
        const data = await mapsAPI.nearby({ keyword, radius, lat, lng });
        if (cancelled) return;
        if (data && data.error === "no_location") {
          setStatus("error");
          setErrMsg(data.message || "Please allow location access and try again.");
          return;
        }
        userRef.current = data.userLocation;
        setSource(data.source || "");
        setPlaces(Array.isArray(data.places) ? data.places : []);
        setStatus("ready");
        persist(data);
      } catch (e) {
        if (cancelled) return;
        setStatus("error");
        setErrMsg("Could not load nearby places. Please try again.");
      }
    };

    const goLive = () => {
      if (typeof navigator !== "undefined" && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => fetchNearby(pos.coords.latitude, pos.coords.longitude),
          () => fetchNearby(null, null), // denied/failed → backend IP fallback
          { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
        );
      } else {
        fetchNearby(null, null);
      }
    };

    if (map_id) {
      mapsAPI.getResult(map_id)
        .then((saved) => {
          if (cancelled) return;
          if (saved && saved.found && Array.isArray(saved.places) && saved.places.length && saved.userLocation) {
            userRef.current = saved.userLocation;
            setSource(saved.source || "");
            setPlaces(saved.places);
            setStatus("ready");
          } else {
            goLive();
          }
        })
        .catch(() => { if (!cancelled) goLive(); });
    } else {
      goLive();
    }

    return () => { cancelled = true; };
  }, [keyword, radius, map_id]);

  // Step 2 — render the Leaflet map once we have a location.
  useEffect(() => {
    if (status !== "ready" || !userRef.current) return;
    let disposed = false;

    const initMap = async () => {
      // Fetch Mappls config for tile key
      let mapConfig = null;
      try {
        mapConfig = await mapsAPI.getConfig();
      } catch (_) {}

      const L = await loadLeaflet();
      if (disposed || !mapElRef.current) return;
      LRef.current = L;
      const u = userRef.current;

      if (mapRef.current) { try { mapRef.current.remove(); } catch (_) {} mapRef.current = null; }
      const map = L.map(mapElRef.current, {
        zoomControl: true, attributionControl: true, scrollWheelZoom: false,
      }).setView([u.lat, u.lng], 15);

      // Use Mappls raster tiles when SDK key is available, otherwise fall back
      // Mappls raster road maps return 412 (Product Not Enabled) on this plan,
      // so we use OpenStreetMap tiles for the UI, but the search data remains Mappls.
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "&copy; OpenStreetMap | Places by Mappls",
      }).addTo(map);
      mapRef.current = map;

      const userIcon = L.divIcon({ className: "", html: userPinHtml(), iconSize: [18, 18], iconAnchor: [9, 9] });
      L.marker([u.lat, u.lng], { icon: userIcon, zIndexOffset: 1000 }).addTo(map).bindPopup("You are here");

      markersRef.current = [];
      places.forEach((p, i) => {
        const icon = L.divIcon({ className: "", html: placePinHtml(i + 1), iconSize: [26, 34], iconAnchor: [13, 34], popupAnchor: [0, -30] });
        const mk = L.marker([p.lat, p.lng], { icon }).addTo(map).bindPopup(placePopupHtml(p));
        mk.on("click", () => setActiveIdx(i));
        markersRef.current.push(mk);
      });

      if (places.length) {
        try {
          const grp = L.featureGroup([L.marker([u.lat, u.lng]), ...markersRef.current]);
          map.fitBounds(grp.getBounds().pad(0.2));
        } catch (_) {}
      }
      // Card mounts inside an animated flex container — nudge Leaflet to
      // recompute its size so tiles aren't clipped/grey.
      setTimeout(() => { try { map.invalidateSize(); } catch (_) {} }, 200);
    };

    initMap().catch(() => { /* map lib blocked/failed — the list below still works */ });

    return () => {
      disposed = true;
      if (mapRef.current) { try { mapRef.current.remove(); } catch (_) {} mapRef.current = null; }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, places]);

  const focusPlace = async (i) => {
    setActiveIdx(i);
    const p = places[i];
    const map = mapRef.current;
    const L = LRef.current;
    const u = userRef.current;
    if (!p) return;
    if (map && L) {
      map.setView([p.lat, p.lng], 16);
      const mk = markersRef.current[i];
      if (mk) mk.openPopup();
      if (u) {
        try {
          const route = await mapsAPI.directions({ from: [u.lat, u.lng], to: [p.lat, p.lng] });
          if (routeRef.current) { try { map.removeLayer(routeRef.current); } catch (_) {} routeRef.current = null; }
          if (route && Array.isArray(route.coordinates) && route.coordinates.length > 1) {
            routeRef.current = L.polyline(route.coordinates, { color: "#f59e0b", weight: 5, opacity: 0.85 }).addTo(map);
            map.fitBounds(routeRef.current.getBounds().pad(0.25));
          }
        } catch (_) { /* routing best-effort */ }
      }
    }
  };

  const title = keyword
    ? `Map Search: ${keyword.charAt(0).toUpperCase()}${keyword.slice(1)}`
    : "Map Search";

  return (
    <div className="rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] overflow-hidden w-full max-w-full min-w-0">
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <MapTrifold weight="duotone" className="w-4 h-4 text-[var(--k-brand)]" />
        <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">{title}</span>
        {userRef.current?.source === "ip" && status === "ready" && (
          <span className="text-[9px] text-muted-foreground/60">(approx · enable location for precise)</span>
        )}
      </div>

      {/* Loading / error states */}
      {(status === "locating" || status === "loading") && (
        <div className="flex items-center gap-2 px-4 py-8 text-sm text-muted-foreground">
          <Spinner weight="bold" className="w-4 h-4 animate-spin text-[var(--k-brand)]" />
          {status === "locating" ? "Getting your location…" : `Finding nearby ${keyword}…`}
        </div>
      )}
      {status === "error" && (
        <div className="flex items-start gap-2 px-4 py-6 text-sm text-muted-foreground">
          <MapPin weight="duotone" className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {/* Map + list */}
      {status === "ready" && (
        <>
          <div
            ref={mapElRef}
            className="w-full h-72 bg-[var(--k-surface-elevated)]"
            style={{ minHeight: "18rem" }}
            data-testid="map-canvas"
          />
          {places.length === 0 ? (
            <div className="px-4 py-4 text-sm text-muted-foreground">
              No {keyword} found. Try a different search term.
            </div>
          ) : (
            <div className="max-h-64 overflow-y-auto divide-y divide-[var(--k-border)]/60">
              {places.map((p, i) => (
                <button
                  key={i}
                  onClick={() => focusPlace(i)}
                  className={`w-full text-left px-4 py-2.5 flex items-start gap-3 transition-colors ${
                    activeIdx === i ? "bg-[var(--k-brand)]/10" : "hover:bg-[var(--k-surface-elevated)]/50"
                  }`}
                >
                  <span className="mt-0.5 shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-500 text-white text-[10px] font-bold">
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-foreground line-clamp-1">{p.name}</span>
                    {p.address && <span className="block text-[11px] text-muted-foreground line-clamp-1">{p.address}</span>}
                  </span>
                  <span className="shrink-0 text-[11px] font-medium text-[var(--k-brand)] whitespace-nowrap mt-0.5">
                    {fmtDist(p.distance)}
                  </span>
                </button>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between px-4 py-2 border-t border-[var(--k-border)]/60">
            <span className="text-[10px] text-muted-foreground/60">
              {places.length} result{places.length === 1 ? "" : "s"} · tap to route
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/50">
              <NavigationArrow weight="duotone" className="w-3 h-3" />
              {source === "mappls" ? "Mappls" : "OpenStreetMap"}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
