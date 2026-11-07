// Turns a typed address into map coordinates using OpenStreetMap's free
// Nominatim service (no API key). Fine for a demo; for production use a paid
// geocoder or the Google Geocoding API.
export type Place = { query: string; label: string; lat: number; lon: number; city: string | null };

export async function geocode(query: string): Promise<Place | null> {
  const params = new URLSearchParams({
    format: "jsonv2",
    addressdetails: "1",
    limit: "1",
    countrycodes: "us",
    // Prefer results around Irvine without blocking results elsewhere.
    viewbox: "-117.90,33.76,-117.69,33.60",
    bounded: "0",
    q: query,
  });
  const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error("Address lookup failed");
  const data = await res.json();
  if (!Array.isArray(data) || data.length === 0) return null;
  const r = data[0];
  const a = r.address ?? {};
  return {
    query,
    label: r.display_name,
    lat: parseFloat(r.lat),
    lon: parseFloat(r.lon),
    city: a.city ?? a.town ?? a.village ?? a.hamlet ?? null,
  };
}
