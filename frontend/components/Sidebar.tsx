"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useProject } from "@/lib/project-context";
import Mark from "./Mark";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/documents", label: "Documents" },
  { href: "/navigator", label: "Navigator" },
  { href: "/search", label: "Search" },
  { href: "/timeline", label: "Timeline" },
  { href: "/questions", label: "Ask the City" },
];
const ITEM_STEP = 46; // 44px target + 2px gap

export default function Sidebar() {
  const pathname = usePathname();
  const { missingPriority, place } = useProject();
  const active = NAV.findIndex((n) => n.href === pathname);
  const missing = missingPriority.length;

  return (
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="ClearPath home">
        <Mark size={28} />
        ClearPath
      </Link>
      <nav aria-label="Main" className={`nav${active >= 0 ? " has-pill" : ""}`}>
        {active >= 0 && <span className="nav-pill" aria-hidden="true" style={{ transform: `translateY(${active * ITEM_STEP}px)` }} />}
        {NAV.map((item) => (
          <Link key={item.href} href={item.href} className="nav-item" aria-current={pathname === item.href ? "page" : undefined}>
            {item.label}
            {item.href === "/documents" && missing > 0 && (
              <span key={missing} className="nav-count num" aria-label={`${missing} documents missing`}>
                {missing}
              </span>
            )}
          </Link>
        ))}
      </nav>
      <div className="side-project">
        <span className="k">Your project</span>
        <span className="v">{place ? place.label : "No address yet"}</span>
        <span className="s">Detached ADU, Irvine</span>
      </div>
    </aside>
  );
}
