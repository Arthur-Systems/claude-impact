import type { Metadata } from "next";
import { ReactNode } from "react";
import { House } from "lucide-react";
import "./globals.css";
import { ProjectProvider } from "@/lib/project-context";
import Splash from "@/components/Splash";
import Mark from "@/components/Mark";
import CommandSearch from "@/components/panels/CommandSearch";
import AskCityButton from "@/components/panels/AskCityButton";

export const metadata: Metadata = {
  title: "ClearPath",
  description: "A guided way through the housing permit process",
};

// Runs before paint: hides the splash at once if it already played this session.
const SPLASH_GATE = `try{if(sessionStorage.getItem("clearpath-splash-seen")==="1")document.documentElement.setAttribute("data-splash","seen")}catch(e){}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SPLASH_GATE }} />
      </head>
      <body>
        <Splash />
        <ProjectProvider>
          <header className="appbar">
            <div className="appbar-inner">
              <div className="appbar-left">
                <a className="appbar-brand" href="/" aria-label="ClearPath home">
                  <Mark size={26} />
                  <span>ClearPath</span>
                </a>
                <span className="project-chip">
                  <House size={16} strokeWidth={1.75} aria-hidden="true" />
                  <span>Detached ADU, Irvine</span>
                </span>
              </div>
              <div className="appbar-right">
                <CommandSearch />
                <AskCityButton />
              </div>
            </div>
          </header>
          <main className="page">
            {children}
            <footer className="site-footer">Prototype. Not legal advice. Confirm with the City of Irvine or a professional.</footer>
          </main>
        </ProjectProvider>
      </body>
    </html>
  );
}
