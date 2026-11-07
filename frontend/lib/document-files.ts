import { listZipEntries } from "./zip";
import type { DocId, UploadedFile } from "./project-context";

// Filename guesses only; document contents are never validated.
export function guessMatch(name: string): Pick<UploadedFile, "matchedTo" | "confidence"> {
  const rules: [RegExp, DocId][] = [
    [/site[ _-]*plan/i, "site"],
    [/floor/i, "floor"],
    [/energy|t24|title[ _-]*24/i, "energy"],
    [/deed|owner|title/i, "ownership"],
    [/struct/i, "structural"],
    [/elev/i, "elevations"],
  ];
  for (const [re, id] of rules) if (re.test(name)) return { matchedTo: id, confidence: "high" };
  return { matchedTo: null, confidence: "none" };
}

export function uniqueNames(existing: string[], incoming: string[]): string[] {
  const seen = new Set(existing.map(name => name.toLowerCase()));
  return incoming.filter(name => {
    const key = name.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export async function expandUpload(file: { name: string; arrayBuffer: () => Promise<ArrayBuffer> }): Promise<string[]> {
  return /\.zip$/i.test(file.name) ? listZipEntries(await file.arrayBuffer()) : [file.name];
}
