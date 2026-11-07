"use client";
import { useEffect, useState } from "react";

// One short brand moment per browser session. The page renders underneath,
// so content is ready when the splash leaves. Any click or key skips it.
const KEY = "clearpath-splash-seen";
const TOTAL_MS = 1150;
const SKIP_MS = 180;
const EXIT_AT_MS = 860; // matches the CSS exit delay

export default function Splash() {
  const [state, setState] = useState<"show" | "exiting" | "leaving" | "gone">("show");

  useEffect(() => {
    // The inline gate in layout.tsx marks <html> before hydration, so this
    // check is stable under React Strict Mode's double effect run.
    const seen = document.documentElement.getAttribute("data-splash") === "seen";
    try {
      sessionStorage.setItem(KEY, "1");
    } catch {
      /* storage blocked: still show once per load */
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (seen || reduce) {
      setState("gone");
      return;
    }
    const exit = window.setTimeout(() => setState((s) => (s === "show" ? "exiting" : s)), EXIT_AT_MS);
    const done = window.setTimeout(() => setState("gone"), TOTAL_MS);
    const skip = () => {
      window.clearTimeout(done);
      window.clearTimeout(exit);
      setState("leaving");
      window.setTimeout(() => setState("gone"), SKIP_MS);
    };
    window.addEventListener("keydown", skip, { once: true });
    window.addEventListener("pointerdown", skip, { once: true });
    return () => {
      window.clearTimeout(exit);
      window.clearTimeout(done);
      window.removeEventListener("keydown", skip);
      window.removeEventListener("pointerdown", skip);
    };
  }, []);

  if (state === "gone") return null;
  return (
    <div className={`splash${state === "leaving" ? " is-leaving" : ""}${state === "exiting" ? " is-exiting" : ""}`} aria-hidden="true">
      <div className="splash-inner">
        <svg className="splash-mark" viewBox="0 0 48 48" width="56" height="56">
          <rect x="1" y="1" width="46" height="46" rx="12" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.35" />
          <path className="splash-path" d="M12 34 L20 26 L27 31 L37 15" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="37" cy="15" r="3.5" fill="#f2b84b" />
        </svg>
        <div>
          <span className="splash-word">ClearPath</span>
          <span className="splash-line">Your ADU permit, step by step.</span>
        </div>
      </div>
    </div>
  );
}
