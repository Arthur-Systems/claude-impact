// Official County of Orange logo slot. No image ships in /public yet, so the
// clean text plate is the default and no request is made. When the file is
// added, set LOGO_SRC to "/oc-logo.png".
const LOGO_SRC: string | null = null;

export default function OcLogo() {
  return (
    <div className="logo-plate">
      {LOGO_SRC ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={LOGO_SRC} alt="County of Orange" />
      ) : (
        <span className="logo-fallback">
          <span className="logo-kicker">Built for</span>
          County of Orange
        </span>
      )}
    </div>
  );
}
