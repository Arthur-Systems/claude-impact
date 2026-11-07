// Stand-in for a Google Maps snapshot. Later: use the Static Maps API image
// built from the user's address.
export default function MapPlaceholder() {
  return (
    <>
      <svg viewBox="0 0 400 190" role="img" aria-label="Map preview of the project address" className="map">
        <rect width="400" height="190" fill="#E9EEE6" />
        <rect x="250" y="20" width="110" height="60" fill="#CFE3CC" />
        <path d="M0 120H400M0 60H400M120 0V190M290 0V190" stroke="#fff" strokeWidth="10" />
        <path d="M0 150L400 40" stroke="#F3E3B5" strokeWidth="7" />
        <circle cx="205" cy="90" r="10" fill="#B3261E" stroke="#fff" strokeWidth="3" />
      </svg>
      <p className="muted">Placeholder for a Google Maps snapshot of the project address</p>
    </>
  );
}
