"use client";
import { useEffect, useRef } from "react";
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
  const navRef = useRef<HTMLElement>(null);

  const sheetRef = useRef<HTMLDialogElement>(null);
  // Close the phone menu sheet after navigating.
  useEffect(() => {
    if (sheetRef.current?.open) sheetRef.current.close();
  }, [pathname]);

  // On the narrow layout the nav is a horizontal pill row: keep the active pill in view.
  useEffect(() => {
    const nav = navRef.current;
    const el = nav?.querySelector<HTMLElement>("[aria-current=page]");
    if (!nav || !el || nav.scrollWidth <= nav.clientWidth) return;
    nav.scrollTo({ left: el.offsetLeft - (nav.clientWidth - el.offsetWidth) / 2, behavior: "auto" });
  }, [pathname]);

  return (
    <aside className="sidebar">
      <div className="topbar">
        <Link href="/" className="brand" aria-label="ClearPath home">
          <Mark size={28} />
          ClearPath
        </Link>
        <button type="button" className="menu-btn" aria-haspopup="dialog" onClick={() => sheetRef.current?.showModal()}>
          Menu
          {missing > 0 && <span className="nav-count num" aria-hidden="true">{missing}</span>}
        </button>
      </div>
      <nav ref={navRef} aria-label="Main" className={`nav${active >= 0 ? " has-pill" : ""}`}>
        {active >= 0 && <span className="nav-pill" aria-hidden="true" style={{ transform: `translateY(${active * ITEM_STEP}px)` }} />}
        {NAV.map((item) => (
          <Link key={item.href} href={item.href} className="nav-item" aria-current={pathname === item.href ? "page" : undefined}>
            {item.label}
            {item.href === "/documents" && missing > 0 && (
              <span key={missing} className="nav-count num" aria-label={`${missing} ${missing === 1 ? "document" : "documents"} missing`}>
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
      <dialog
        ref={sheetRef}
        className="sheet"
        aria-label="Menu"
        onClick={(e) => {
          if (e.target === e.currentTarget) e.currentTarget.close();
        }}
      >
        <div className="sheet-head">
          <span className="brand">
            <Mark size={24} />
            ClearPath
          </span>
          <button type="button" className="menu-btn" onClick={() => sheetRef.current?.close()}>
            Close
          </button>
        </div>
        <nav aria-label="Main menu" className="sheet-nav">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="nav-item" aria-current={pathname === item.href ? "page" : undefined}>
              {item.label}
              {item.href === "/documents" && missing > 0 && (
                <span className="nav-count num" aria-label={`${missing} ${missing === 1 ? "document" : "documents"} missing`}>
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
      </dialog>
    </aside>
  );
}
