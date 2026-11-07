"use client";
// STUB. The charts implementer replaces this file.
// Contract: pure SVG donut, props only, no context.
export default function ReadinessRing({ ready, total, size = 64 }: { ready: number; total: number; size?: number }) {
  return <div role="img" aria-label={`${ready} of ${total} documents ready`} style={{ width: size, height: size }} />;
}
