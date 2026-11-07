"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { ExternalLink, MapPin, Minus, Plus, Search, TriangleAlert } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
import { geocode } from "@/lib/geocode";
import { useProject } from "@/lib/project-context";
import s from "./map.module.css";

const STYLE = "https://tiles.openfreemap.org/styles/positron";
const IRVINE: [number, number] = [-117.8, 33.68];

function hasWebGL() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

function reducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function gmaps(lat: number, lon: number) {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
}

// Tint the Positron style to the ClearPath palette.
function tint(map: any) {
  const layers: any[] = map.getStyle()?.layers ?? [];
  for (const l of layers) {
    const sl: string = l["source-layer"] ?? "";
    const id: string = l.id ?? "";
    try {
      if (l.type === "fill" && sl === "water") map.setPaintProperty(id, "fill-color", "#cfe9e2");
      else if (l.type === "line" && sl === "waterway") map.setPaintProperty(id, "line-color", "#cfe9e2");
      else if (l.type === "fill" && (sl === "park" || /park|wood|grass|landcover|landuse/.test(id)))
        map.setPaintProperty(id, "fill-color", "#e6f1ed");
      else if (l.type === "background") map.setPaintProperty(id, "background-color", "#f6f5f1");
      else if (l.type === "line" && sl === "transportation") map.setPaintProperty(id, "line-color", "#ffffff");
      else if (l.type === "fill" && sl === "building") map.setPaintProperty(id, "fill-color", "#ebe8e0");
      else if (l.type === "symbol") {
        map.setPaintProperty(id, "text-color", "#4a524f");
        map.setPaintProperty(id, "text-halo-color", "#f6f5f1");
      }
    } catch {
      /* layer may not support this property */
    }
  }
  try {
    const src = Object.keys(map.getStyle().sources).find((k) => map.getSource(k)?.type === "vector");
    if (src && !map.getLayer("cp-3d")) {
      map.addLayer({
        id: "cp-3d",
        type: "fill-extrusion",
        source: src,
        "source-layer": "building",
        minzoom: 15,
        paint: {
          "fill-extrusion-color": "#e3e0d6",
          "fill-extrusion-height": ["coalesce", ["get", "render_height"], 6],
          "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
          "fill-extrusion-opacity": 0.75,
        },
      });
    }
  } catch {
    /* 3D buildings are optional */
  }
}

export default function MapCard() {
  const { place, setPlace } = useProject();
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const libRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState(place?.query ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hasWebGL()) {
      setFailed(true);
      return;
    }
    let map: any;
    let cancelled = false;
    import("maplibre-gl")
      .then((mod) => {
        if (cancelled || !box.current) return;
        const maplibregl: any = (mod as any).default ?? mod;
        libRef.current = maplibregl;
        // Next/webpack cannot resolve MapLibre's default worker path; point it at the bundled asset.
        try {
          maplibregl.setWorkerUrl?.(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).href);
        } catch {
          /* keep the default worker URL */
        }
        map = new maplibregl.Map({
          container: box.current,
          style: STYLE,
          center: IRVINE,
          zoom: 11.3,
          scrollZoom: false,
          dragPan: true,
          doubleClickZoom: true,
          attributionControl: { compact: true },
        });
        mapRef.current = map;
        let loaded = false;
        map.on("load", () => {
          loaded = true;
          tint(map);
          setReady(true);
        });
        map.on("error", () => {
          if (!loaded) setFailed(true);
        });
      })
      .catch(() => setFailed(true));
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const lib = libRef.current;
    if (!ready || !map || !lib) return;
    markerRef.current?.remove();
    markerRef.current = null;
    if (!place) return;
    const el = document.createElement("div");
    el.className = s.marker;
    el.innerHTML = `<span class="${s.halo}"></span><span class="${s.dot}"></span>`;
    markerRef.current = new lib.Marker({ element: el }).setLngLat([place.lon, place.lat]).addTo(map);
    const target = { center: [place.lon, place.lat], zoom: 16.5, pitch: 45, bearing: -17 };
    if (reducedMotion()) map.jumpTo(target);
    else map.flyTo({ ...target, duration: 1200, essential: false });
  }, [place, ready]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (q.length < 5) {
      setError("Enter a street address, for example 1 Civic Center Plaza.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const p = await geocode(q);
      if (!p) setError("We could not find that address. Check the spelling and add the city.");
      else setPlace(p);
    } catch {
      setError("The map lookup is not reachable right now. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  const outsideIrvine = place && place.city && place.city.toLowerCase() !== "irvine";
  const short = place ? place.label.split(",")[0] : "";

  return (
    <section className={s.card} aria-label="Project map">
      {failed ? (
        <div className={s.fallback}>
          <MapPin size={20} strokeWidth={1.75} aria-hidden />
          <span>{place ? place.label : "Irvine, CA"}</span>
          <a href={place ? gmaps(place.lat, place.lon) : "https://www.google.com/maps/search/?api=1&query=Irvine%2C%20CA"} target="_blank" rel="noopener noreferrer" className={s.link}>
            <ExternalLink size={16} strokeWidth={2} aria-hidden /> Google Maps
          </a>
        </div>
      ) : (
        <div ref={box} className={s.map} role="region" aria-label={place ? `Map showing ${place.label}` : "Map of Irvine"} />
      )}

      <div className={s.top}>
        <form onSubmit={onSubmit} className={s.search} role="search">
          <Search size={18} strokeWidth={2} aria-hidden className={s.searchIcon} />
          <label htmlFor="map-search" className={s.sr}>Project address</label>
          <input
            id="map-search"
            className={s.input}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="1 Civic Center Plaza, Irvine"
            aria-describedby={error ? "map-search-error" : undefined}
            aria-invalid={error ? true : undefined}
            autoComplete="street-address"
          />
          <button type="submit" className={s.go} disabled={busy} aria-label={busy ? "Finding address" : "Find address"}>
            {busy ? <span className={s.spin} aria-hidden /> : <MapPin size={18} strokeWidth={2} aria-hidden />}
          </button>
        </form>
        {error && (
          <p id="map-search-error" role="alert" className={s.error}>{error}</p>
        )}
        {outsideIrvine && (
          <p role="status" className={s.warn}>
            <TriangleAlert size={16} strokeWidth={2} aria-hidden />
            This address looks like it is in {place?.city}. ClearPath currently supports Irvine only.
          </p>
        )}
      </div>

      {!failed && (
        <div className={s.zoom}>
          <button type="button" className={s.zbtn} aria-label="Zoom in" onClick={() => mapRef.current?.zoomIn()}>
            <Plus size={18} strokeWidth={2} aria-hidden />
          </button>
          <button type="button" className={s.zbtn} aria-label="Zoom out" onClick={() => mapRef.current?.zoomOut()}>
            <Minus size={18} strokeWidth={2} aria-hidden />
          </button>
        </div>
      )}

      {place && !failed && (
        <div className={s.chip}>
          <MapPin size={16} strokeWidth={2} aria-hidden className={s.chipIcon} />
          <span className={s.chipText} title={place.label}>{short}</span>
          <a href={gmaps(place.lat, place.lon)} target="_blank" rel="noopener noreferrer" className={s.chipLink} aria-label="Open in Google Maps">
            <ExternalLink size={16} strokeWidth={2} aria-hidden />
          </a>
        </div>
      )}
    </section>
  );
}
