import { ReactNode } from "react";

// Re-mounts on every route change, so each page gets a short enter transition.
export default function Template({ children }: { children: ReactNode }) {
  return <div className="route-enter">{children}</div>;
}
