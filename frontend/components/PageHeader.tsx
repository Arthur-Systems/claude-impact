import { ReactNode } from "react";

// Every page answers: what is happening, what can I do, what should I do next.
export default function PageHeader({
  title,
  status,
  next,
  action,
}: {
  title: string;
  status: string;
  next: string;
  action?: ReactNode;
}) {
  return (
    <>
      <h1>{title}</h1>
      <p className="status">{status}</p>
      <div className="next">
        <div>
          <b>Next step:</b> {next}
        </div>
        {action}
      </div>
    </>
  );
}
