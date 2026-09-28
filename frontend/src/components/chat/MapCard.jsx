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
import { Map, MapMarker, MarkerContent, MapPopup, MapControls, MapRoute } from "@/components/ui/map";

export function fmtDist(m) {
  if (m == null || isNaN(m)) return "";
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

export function MapCard({ keyword = "places", radius = 3000, map_id }) {
  const mapRef = useRef(null);
  const userRef = useRef(null); // {lat,lng,label,source}

  const [status, setStatus] = useState("locating"); // locating | loading | ready | error
  const [places, setPlaces] = useState([]);
  const [errMsg, setErrMsg] = useState("");
  const [activeIdx, setActiveIdx] = useState(-1);
  const [source, setSource] = useState("");
  
  const [viewport, setViewport] = useState(null);
  const [routeCoordinates, setRouteCoordinates] = useState(null);

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
        setViewport({ center: [data.userLocation.lng, data.userLocation.lat], zoom: 15 });
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
            setViewport({ center: [saved.userLocation.lng, saved.userLocation.lat], zoom: 15 });
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

  useEffect(() => {
     if (status !== "ready" || !userRef.current || !mapRef.current) return;
     if (places.length > 0) {
       import("maplibre-gl").then((maplibre) => {
         try {
           const bounds = new maplibre.LngLatBounds();
           bounds.extend([userRef.current.lng, userRef.current.lat]);
           places.forEach(p => bounds.extend([p.lng, p.lat]));
           mapRef.current.fitBounds(bounds, { padding: 40 });
         } catch (_) {}
       });
     }
  }, [status, places]);

  const focusPlace = async (i) => {
    setActiveIdx(i);
    const p = places[i];
    const map = mapRef.current;
    const u = userRef.current;
    if (!p) return;
    
    if (map) {
      map.flyTo({ center: [p.lng, p.lat], zoom: 16 });
      
      if (u) {
        try {
          const route = await mapsAPI.directions({ from: [u.lat, u.lng], to: [p.lat, p.lng] });
          if (route && Array.isArray(route.coordinates) && route.coordinates.length > 1) {
             const geojsonCoords = route.coordinates.map(c => [c[1], c[0]]);
             setRouteCoordinates(geojsonCoords);
             
             import("maplibre-gl").then((maplibre) => {
               try {
                 const bounds = new maplibre.LngLatBounds();
                 geojsonCoords.forEach(c => bounds.extend(c));
                 map.fitBounds(bounds, { padding: 50 });
               } catch (_) {}
             });
          } else {
             setRouteCoordinates(null);
          }
        } catch (_) { setRouteCoordinates(null); }
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

      {status === "ready" && viewport && (
        <>
          <div className="w-full h-72 bg-[var(--k-surface-elevated)] relative" style={{ minHeight: "18rem" }}>
            <Map 
              ref={mapRef}
              viewport={viewport} 
              onViewportChange={setViewport}
            >
               <MapControls />
               
               <MapMarker longitude={userRef.current.lng} latitude={userRef.current.lat} onClick={() => setActiveIdx(-2)}>
                  <MarkerContent>
                    <div style={{width: 18, height: 18, borderRadius: "50%", background: "#2563eb", border: "3px solid #fff", boxShadow: "0 0 0 2px rgba(37,99,235,.45)"}} />
                  </MarkerContent>
               </MapMarker>
               {activeIdx === -2 && (
                 <MapPopup 
                    longitude={userRef.current.lng} 
                    latitude={userRef.current.lat}
                    closeButton={true}
                    onClose={() => setActiveIdx(-1)}
                 >
                    <div className="font-semibold text-sm">You are here</div>
                 </MapPopup>
               )}
               
               {places.map((p, i) => (
                  <MapMarker key={i} longitude={p.lng} latitude={p.lat} onClick={() => focusPlace(i)}>
                    <MarkerContent>
                      <div style={{position: "relative", width: 26, height: 34}}>
                        <svg width="26" height="34" viewBox="0 0 26 34" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M13 0C5.82 0 0 5.82 0 13c0 9.25 13 21 13 21s13-11.75 13-21C26 5.82 20.18 0 13 0z" fill="#e11d48"/>
                          <circle cx="13" cy="13" r="9" fill="#fff"/>
                        </svg>
                        <span style={{position: "absolute", top: 3, left: 0, width: 26, textAlign: "center", font: "700 12px system-ui", color: "#e11d48"}}>{i + 1}</span>
                      </div>
                    </MarkerContent>
                  </MapMarker>
               ))}
               
               {activeIdx >= 0 && places[activeIdx] && (
                 <MapPopup 
                    longitude={places[activeIdx].lng} 
                    latitude={places[activeIdx].lat}
                    closeButton={true}
                    onClose={() => setActiveIdx(-1)}
                 >
                    <div style={{minWidth: 160, font: "13px system-ui", lineHeight: 1.35}}>
                      <div style={{fontWeight: 700, marginBottom: 2}}>{places[activeIdx].name}</div>
                      {places[activeIdx].address && <div style={{color: "#666", fontSize: 11, marginBottom: 4}}>{places[activeIdx].address}</div>}
                      <div style={{color: "#e11d48", fontSize: 11, fontWeight: 600, marginBottom: 4}}>{fmtDist(places[activeIdx].distance)} away</div>
                      <a href={`https://www.google.com/maps/dir/?api=1&destination=${places[activeIdx].lat},${places[activeIdx].lng}`} target="_blank" rel="noopener noreferrer" style={{color: "#2563eb", fontSize: 12, fontWeight: 600}}>Directions &#8599;</a>
                    </div>
                 </MapPopup>
               )}
               
               {routeCoordinates && (
                 <MapRoute coordinates={routeCoordinates} color="#f59e0b" width={5} opacity={0.85} />
               )}
            </Map>
          </div>
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
              mapcn (MapLibre)
            </span>
          </div>
        </>
      )}
    </div>
  );
}
