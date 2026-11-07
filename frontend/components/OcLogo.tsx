"use client";
import { useState } from "react";

// Shows the official logo from /public/oc-logo.png.
// If the file is not there yet, it falls back to a plain text label.
export default function OcLogo() {
  const [failed, setFailed] = useState(false);
  return (
    <div className="logo-plate">
      {failed ? (
        <span className="logo-fallback">County of Orange</span>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="/oc-logo.png" alt="County of Orange" onError={() => setFailed(true)} />
      )}
    </div>
  );
}
