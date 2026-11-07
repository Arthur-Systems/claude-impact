"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useProject } from "@/lib/project-context";
import OcLogo from "./OcLogo";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/documents", label: "Documents" },
  { href: "/navigator", label: "Navigator" },
  { href: "/search", label: "Search" },
  { href: "/timeline", label: "Timeline" },
  { href: "/questions", label: "Ask the City" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { missingPriority } = useProject();

  return (
    <aside className="sidebar">
      <p className="brand">ClearPath</p>
      <nav aria-label="Main">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={pathname === item.href ? "page" : undefined}
          >
            {item.label}
            {item.href === "/documents" && missingPriority.length > 0 && (
              <span className="chip pri">{missingPriority.length} priority</span>
            )}
          </Link>
        ))}
      </nav>
      <OcLogo />
    </aside>
  );
}
