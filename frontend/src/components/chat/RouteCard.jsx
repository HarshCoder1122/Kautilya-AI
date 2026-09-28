import { useEffect, useRef, useState } from "react";
import { NavigationArrow, MapPin, Spinner, FlagCheckered } from "@phosphor-icons/react";
import { mapsAPI } from "../../lib/api";
import { fmtDist } from "./MapCard";
import { Map, MapMarker, MarkerContent, MarkerPopup, MapControls, MapRoute } from "@/components/ui/map";

function fmtEta(s) {
  if (s == null || isNaN(s)) return "";
  const mins = Math.round(s / 60);
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function RouteCard({ origin = "", destination = "", map_id }) {
  const mapRef = useRef(null);

  const [status, setStatus] = useState("locating"); // locating | loading | ready | error
  const [errMsg, setErrMsg] = useState("");
  const [resolved, setResolved] = useState(null); // {origin, destination, route}
  
  const [viewport, setViewport] = useState(null);

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
        setViewport({ center: [data.origin.lng, data.origin.lat], zoom: 12 });
        setStatus("ready");
        persist(data);
      } catch (e) {
        if (cancelled) return;
        setStatus("error");
        setErrMsg("Couldn't plan that route. Please try again.");
      }
    };

    const goLive = () => {
      if (origin) {
        callRoute(undefined);
        return;
      }
      if (typeof navigator !== "undefined" && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => callRoute([pos.coords.latitude, pos.coords.longitude]),
          () => callRoute(undefined),
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
            setViewport({ center: [saved.origin.lng, saved.origin.lat], zoom: 12 });
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
  }, [origin, destination, map_id]);

  useEffect(() => {
    if (status !== "ready" || !resolved || !resolved.origin || !resolved.destination || !mapRef.current) return;
    import("maplibre-gl").then((maplibre) => {
      try {
        const bounds = new maplibre.LngLatBounds();
        bounds.extend([resolved.origin.lng, resolved.origin.lat]);
        bounds.extend([resolved.destination.lng, resolved.destination.lat]);
        
        if (resolved.route && Array.isArray(resolved.route.coordinates) && resolved.route.coordinates.length > 0) {
          const coords = resolved.route.coordinates.map(c => [c[1], c[0]]);
          coords.forEach(c => bounds.extend(c));
        }
        
        mapRef.current.fitBounds(bounds, { padding: 40 });
      } catch (_) {}
    });
  }, [status, resolved]);

  const route = resolved && resolved.route;
  const dist = route && fmtDist(route.distance_m);
  const eta = route && fmtEta(route.duration_s);
  const destLabel = (resolved && resolved.destination && resolved.destination.label) || destination || "destination";

  let routeCoords = null;
  if (route && Array.isArray(route.coordinates) && route.coordinates.length > 1) {
    routeCoords = route.coordinates.map(c => [c[1], c[0]]);
  } else if (resolved && resolved.origin && resolved.destination) {
    // straight line fallback
    routeCoords = [
      [resolved.origin.lng, resolved.origin.lat],
      [resolved.destination.lng, resolved.destination.lat]
    ];
  }

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

      {status === "ready" && resolved && viewport && (
        <>
          <div className="w-full h-72 bg-[var(--k-surface-elevated)] relative" style={{ minHeight: "18rem" }}>
            <Map 
              ref={mapRef}
              viewport={viewport} 
              onViewportChange={setViewport}
            >
               <MapControls />
               
               {/* Origin Marker */}
               <MapMarker longitude={resolved.origin.lng} latitude={resolved.origin.lat}>
                  <MarkerContent>
                    <div style={{position: "relative", width: 26, height: 34}}>
                      <svg width="26" height="34" viewBox="0 0 26 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M13 0C5.82 0 0 5.82 0 13c0 9.25 13 21 13 21s13-11.75 13-21C26 5.82 20.18 0 13 0z" fill="#16a34a"/>
                        <circle cx="13" cy="13" r="9" fill="#fff"/>
                      </svg>
                      <span style={{position: "absolute", top: 3, left: 0, width: 26, textAlign: "center", font: "700 12px system-ui", color: "#16a34a"}}>A</span>
                    </div>
                  </MarkerContent>
                  <MarkerPopup>
                     <div>
                       <b>From</b><br/>{resolved.origin.label || "Start"}
                     </div>
                  </MarkerPopup>
               </MapMarker>
               
               {/* Destination Marker */}
               <MapMarker longitude={resolved.destination.lng} latitude={resolved.destination.lat}>
                  <MarkerContent>
                    <div style={{position: "relative", width: 26, height: 34}}>
                      <svg width="26" height="34" viewBox="0 0 26 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M13 0C5.82 0 0 5.82 0 13c0 9.25 13 21 13 21s13-11.75 13-21C26 5.82 20.18 0 13 0z" fill="#e11d48"/>
                        <circle cx="13" cy="13" r="9" fill="#fff"/>
                      </svg>
                      <span style={{position: "absolute", top: 3, left: 0, width: 26, textAlign: "center", font: "700 12px system-ui", color: "#e11d48"}}>B</span>
                    </div>
                  </MarkerContent>
                  <MarkerPopup>
                     <div>
                       <b>To</b><br/>{resolved.destination.label || "Destination"}
                     </div>
                  </MarkerPopup>
               </MapMarker>
               
               {/* Route Line */}
               {routeCoords && (
                 <MapRoute 
                    coordinates={routeCoords} 
                    color={route ? "#f59e0b" : "#94a3b8"} 
                    width={route ? 5 : 3} 
                    opacity={0.9} 
                    dashArray={route ? undefined : [6, 8]}
                 />
               )}
            </Map>
          </div>
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
