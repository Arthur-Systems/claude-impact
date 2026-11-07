import type { Metadata } from "next";
import { ReactNode } from "react";
import "./globals.css";
import { ProjectProvider } from "@/lib/project-context";
import Sidebar from "@/components/Sidebar";
import Splash from "@/components/Splash";

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
          <div className="shell">
            <Sidebar />
            <main className="main">
              <div className="main-inner">
                {children}
                <footer className="site-footer">Prototype. Not legal advice. Confirm with the City of Irvine or a professional.</footer>
              </div>
            </main>
          </div>
        </ProjectProvider>
      </body>
    </html>
  );
}
