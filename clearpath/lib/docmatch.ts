// Matches an uploaded file name to a live checklist requirement key by name only.
export type ReqRef = { key: string; title: string };

// Most specific first.
const ALIASES: [string, string[]][] = [
  ["address-application", ["address application", "address"]],
  ["adu-permit-application", ["permit application"]],
  ["adu-verification-form", ["verification"]],
  ["building-plans-calcs", ["building plans", "calculations", "plans", "calcs"]],
  ["development-standards-checklist", ["development standards", "standards checklist", "67 01"]],
  ["covenant", ["covenant"]],
  ["signed-affidavit-esig", ["affidavit"]],
  ["developer-deposit-case-setup", ["developer deposit", "deposit"]],
  ["school-fee-determination-form", ["school fee", "school"]],
  ["tca-form", ["tca", "transportation corridor"]],
];

export function normalizeName(fileName: string): string {
  const base = fileName.split(/[\\/]/).pop() ?? fileName;
  const noExt = base.replace(/\.[^.]+$/, "");
  return noExt.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
}

function hasPhrase(name: string, phrase: string): boolean {
  return ` ${name} `.includes(` ${phrase} `);
}

export function matchRequirement(fileName: string, reqs: ReqRef[]): string | null {
  const name = normalizeName(fileName);
  const keys = new Set(reqs.map((r) => r.key));
  for (const [key, phrases] of ALIASES) {
    if (!keys.has(key)) continue;
    if (phrases.some((ph) => hasPhrase(name, ph))) return key;
  }
  const aliased = new Set(ALIASES.map(([k]) => k));
  for (const r of reqs) {
    if (aliased.has(r.key)) continue;
    const words = normalizeName(r.title + ".x").split(" ").filter((w) => w.length >= 4);
    if (words.length && words.every((w) => hasPhrase(name, w))) return r.key;
  }
  return null;
}
