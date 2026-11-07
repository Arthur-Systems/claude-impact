"use client";
import { FormEvent, useState } from "react";
import { geocode } from "@/lib/geocode";
import { useProject } from "@/lib/project-context";

// Real, working map: OpenStreetMap embed (no API key needed).
// Later you can swap the iframe for a Google Static Maps image.
const IRVINE_BBOX = "-117.88,33.64,-117.74,33.74";

export default function AddressMap() {
  const { place, setPlace } = useProject();
  const [query, setQuery] = useState(place?.query ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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

  const bbox = place
    ? `${place.lon - 0.004},${place.lat - 0.0025},${place.lon + 0.004},${place.lat + 0.0025}`
    : IRVINE_BBOX;
  const src =
    `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik` +
    (place ? `&marker=${place.lat},${place.lon}` : "");
  const outsideIrvine = place && place.city && place.city.toLowerCase() !== "irvine";

  return (
    <>
      <form onSubmit={onSubmit} className="inline-form">
        <div className="grow">
          <label htmlFor="addr">Project address</label>
          <input
            id="addr"
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="1 Civic Center Plaza, Irvine"
            aria-describedby={error ? "addr-error" : undefined}
            aria-invalid={error ? true : undefined}
            autoComplete="street-address"
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Finding..." : "Find on map"}
        </button>
      </form>
      {error && (
        <p id="addr-error" role="alert" className="error">
          {error}
        </p>
      )}
      {outsideIrvine && (
        <p role="status" className="notice notice-warn notice-plain">
          This address looks like it is in {place?.city}. ClearPath currently supports Irvine only.
        </p>
      )}
      <iframe title={place ? `Map showing ${place.label}` : "Map of Irvine"} src={src} className="map-frame" loading="lazy" />
      <p className="muted" style={{ margin: 0 }}>
        {place ? (
          <>
            {place.label}.{" "}
            <a href={`https://www.google.com/maps/search/?api=1&query=${place.lat},${place.lon}`} target="_blank" rel="noopener noreferrer">
              Open in Google Maps
            </a>
          </>
        ) : (
          "Map data from OpenStreetMap."
        )}
      </p>
    </>
  );
}
