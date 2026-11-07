// ClearPath brand mark: a path that rises to a clear point.
export default function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} aria-hidden="true" focusable="false">
      <rect x="1" y="1" width="46" height="46" rx="12" fill="none" stroke="currentColor" strokeWidth="2.5" opacity="0.35" />
      <path d="M12 34 L20 26 L27 31 L37 15" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="37" cy="15" r="3.5" fill="#f2b84b" />
    </svg>
  );
}
