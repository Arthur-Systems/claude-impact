import { ReactNode } from "react";

// Title plus one short subtitle. Pages add at most one notice themselves.
export default function PageHeader({ title, subtitle, children }: { title: string; subtitle: string; children?: ReactNode }) {
  return (
    <header className="page-head">
      <h1>{title}</h1>
      <p>{subtitle}</p>
      {children}
    </header>
  );
}
