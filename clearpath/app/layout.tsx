import type { Metadata } from "next";
import { ReactNode } from "react";
import "./globals.css";
import { ProjectProvider } from "@/lib/project-context";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "ClearPath",
  description: "A guided way through the housing permit process",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ProjectProvider>
          <div className="shell">
            <Sidebar />
            <main>{children}</main>
          </div>
        </ProjectProvider>
      </body>
    </html>
  );
}
