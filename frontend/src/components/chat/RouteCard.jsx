/**
 * In-chat journey / route card.
 *
 * Triggered by [ROUTE_PLAN: origin | destination] (origin omitted → user's live
 * location). The backend geocodes both ends + computes the driving route; this
 * card draws origin/destination markers + the route polyline with distance/ETA.
 * Results persist to Firestore (map_id) so reopening the chat restores them.
 */
import { useEffect, useRef, useState } from "react";
import { NavigationArrow, MapPin, Spinner, FlagCheckered } from "@phosphor-icons/react";
import { mapsAPI } from "../../lib/api";
import { loadLeaflet, fmtDist, escapeHtml } from "./MapCard";

function fmtEta(s) {
  if (s == null || isNaN(s)) return "";
  const mins = Math.round(s / 60);
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

function endpointPinHtml(letter, color) {
  return `<div style="position:relative;width:26px;height:34px;">
    <svg width="26" height="34" viewBox="0 0 26 34" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M13 0C5.82 0 0 5.82 0 13c0 9.25 13 21 13 21s13-11.75 13-21C26 5.82 20.18 0 13 0z" fill="${color}"/>
      <circle cx="13" cy="13" r="9" fill="#fff"/>
    </svg>
    <span style="position:absolute;top:3px;left:0;width:26px;text-align:center;font:700 12px system-ui;color:${color};">${letter}</span>
  </div>`;
}

export function RouteCard({ origin = "", destination = "", map_id }) {
  const mapElRef = useRef(null);
  const mapRef = useRef(null);
  const LRef = useRef(null);

  const [status, setStatus] = useState("locating"); // locating | loading | ready | error
  const [errMsg, setErrMsg] = useState("");
  const [resolved, setResolved] = useState(null); // {origin, destination, route}

  // Step 1 — restore saved route, else geocode + compute (live).
  useEffect(() => {
    let cancelled = false;

    const persist = (data) => {
      if (!map_id || !data || !data.origin || !data.destination) return;
      mapsAPI.saveResult({
        map_id, mode: "route",
        origin: data.origin, destination: data.destination, route: data.route,
      }).catch(() => {});
    };

    const callRoute = async (fromCoords) => {
      try {
        setStatus("loading");
        const data = await mapsAPI.route({
          origin: origin || undefined,
          destination,
          from: fromCoords,
        });
        if (cancelled) return;
        if (!data || data.error) {
          setStatus("error");
          setErrMsg((data && data.message) || "Couldn't plan that route.");
          return;
        }
        setResolved(data);
        setStatus("ready");
        persist(data);
      } catch (e) {
        if (cancelled) return;
        setStatus("error");
        setErrMsg("Couldn't plan that route. Please try again.");
      }
    };

    const goLive = () => {
      // Named origin → backend geocodes it (no GPS needed). Empty origin →
      // start from the user's live location (permission popup).
      if (origin) {
        callRoute(undefined);
        return;
      }
      if (typeof navigator !== "undefined" && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => callRoute([pos.coords.latitude, pos.coords.longitude]),
          () => callRoute(undefined), // denied → backend IP fallback (from=none)
          { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
        );
      } else {
        callRoute(undefined);
      }
    };

    if (map_id) {
      mapsAPI.getResult(map_id)
        .then((saved) => {
          if (cancelled) return;
          if (saved && saved.found && saved.origin && saved.destination) {
            setResolved({ origin: saved.origin, destination: saved.destination, route: saved.route || null });
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin, destination, map_id]);

  // Step 2 — draw the map.
  useEffect(() => {
    if (status !== "ready" || !resolved || !resolved.origin || !resolved.destination) return;
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
      const o = resolved.origin, d = resolved.destination;

      if (mapRef.current) { try { mapRef.current.remove(); } catch (_) {} mapRef.current = null; }
      const map = L.map(mapElRef.current, {
        zoomControl: true, attributionControl: true, scrollWheelZoom: false,
      }).setView([o.lat, o.lng], 12);

      // Mappls serves only SATELLITE raster XYZ tiles (`bhuvan_imagery`) on this
      // Mappls raster road maps return 412 (Product Not Enabled) on this plan,
      // so we use OpenStreetMap tiles for the UI, but the search data remains Mappls.
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "&copy; OpenStreetMap",
      }).addTo(map);
      mapRef.current = map;

      const oIcon = L.divIcon({ className: "", html: endpointPinHtml("A", "#16a34a"), iconSize: [26, 34], iconAnchor: [13, 34], popupAnchor: [0, -30] });
      const dIcon = L.divIcon({ className: "", html: endpointPinHtml("B", "#e11d48"), iconSize: [26, 34], iconAnchor: [13, 34], popupAnchor: [0, -30] });
      const oM = L.marker([o.lat, o.lng], { icon: oIcon }).addTo(map).bindPopup(`<b>From</b><br>${escapeHtml(o.label || "Start")}`);
      const dM = L.marker([d.lat, d.lng], { icon: dIcon }).addTo(map).bindPopup(`<b>To</b><br>${escapeHtml(d.label || "Destination")}`);

      let line;
      const coords = resolved.route && Array.isArray(resolved.route.coordinates) ? resolved.route.coordinates : null;
      if (coords && coords.length > 1) {
        line = L.polyline(coords, { color: "#f59e0b", weight: 5, opacity: 0.9 }).addTo(map);
      } else {
        // No road geometry — show a dashed straight line so the journey is still visible.
        line = L.polyline([[o.lat, o.lng], [d.lat, d.lng]], { color: "#94a3b8", weight: 3, opacity: 0.8, dashArray: "6 8" }).addTo(map);
      }
      try {
        const grp = L.featureGroup([oM, dM, line]);
        map.fitBounds(grp.getBounds().pad(0.2));
      } catch (_) {}
      setTimeout(() => { try { map.invalidateSize(); } catch (_) {} }, 200);
    };

    initMap().catch(() => { /* map lib blocked — summary still renders */ });

    return () => {
      disposed = true;
      if (mapRef.current) { try { mapRef.current.remove(); } catch (_) {} mapRef.current = null; }
    };
  }, [status, resolved]);

  const route = resolved && resolved.route;
  const dist = route && fmtDist(route.distance_m);
  const eta = route && fmtEta(route.duration_s);
  const destLabel = (resolved && resolved.destination && resolved.destination.label) || destination || "destination";

  return (
    <div className="rounded-xl border border-[var(--k-border)] bg-[var(--k-surface)] overflow-hidden w-full max-w-full min-w-0">
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <NavigationArrow weight="duotone" className="w-4 h-4 text-[var(--k-brand)]" />
        <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground line-clamp-1">
          Route · {destLabel}
        </span>
      </div>

      {(status === "locating" || status === "loading") && (
        <div className="flex items-center gap-2 px-4 py-8 text-sm text-muted-foreground">
          <Spinner weight="bold" className="w-4 h-4 animate-spin text-[var(--k-brand)]" />
          {status === "locating" ? "Getting your location…" : "Planning the route…"}
        </div>
      )}
      {status === "error" && (
        <div className="flex items-start gap-2 px-4 py-6 text-sm text-muted-foreground">
          <MapPin weight="duotone" className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {status === "ready" && resolved && (
        <>
          <div ref={mapElRef} className="w-full h-72 bg-[var(--k-surface-elevated)]" style={{ minHeight: "18rem" }} data-testid="route-canvas" />
          <div className="px-4 py-2.5 space-y-1.5">
            <div className="flex items-center gap-2 text-[13px]">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-600 text-white text-[10px] font-bold shrink-0">A</span>
              <span className="text-foreground line-clamp-1">{(resolved.origin && resolved.origin.label) || origin || "Your location"}</span>
            </div>
            <div className="flex items-center gap-2 text-[13px]">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-500 text-white text-[10px] font-bold shrink-0">B</span>
              <span className="text-foreground line-clamp-1">{(resolved.destination && resolved.destination.label) || destination}</span>
            </div>
          </div>
          <div className="flex items-center justify-between px-4 py-2 border-t border-[var(--k-border)]/60">
            {route ? (
              <span className="inline-flex items-center gap-3 text-[12px] font-medium text-foreground">
                <span className="inline-flex items-center gap-1"><FlagCheckered weight="duotone" className="w-3.5 h-3.5 text-[var(--k-brand)]" />{dist}</span>
                {eta && <span className="text-muted-foreground">· {eta} drive</span>}
              </span>
            ) : (
              <span className="text-[11px] text-muted-foreground/70">Straight-line distance shown — driving route unavailable</span>
            )}
            {resolved.origin && resolved.destination && (
              <a
                href={`https://www.google.com/maps/dir/?api=1&origin=${resolved.origin.lat},${resolved.origin.lng}&destination=${resolved.destination.lat},${resolved.destination.lng}`}
                target="_blank" rel="noopener noreferrer"
                className="text-[11px] font-semibold text-[var(--k-brand)] hover:underline"
              >
                Open ↗
              </a>
            )}
          </div>
        </>
      )}
    </div>
  );
}
