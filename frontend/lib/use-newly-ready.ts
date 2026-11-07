"use client";
import { useEffect, useRef, useState } from "react";

// Returns ids that became ready since the previous render, so their rows can
// flash once. The first render never flashes.
export function useNewlyReady(readyIds: string[]): string[] {
  const prev = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<string[]>([]);
  const sig = readyIds.join(",");
  useEffect(() => {
    if (prev.current) {
      const p = prev.current;
      const added = readyIds.filter((id) => !p.has(id));
      setFresh(added);
    }
    prev.current = new Set(readyIds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);
  return fresh;
}
