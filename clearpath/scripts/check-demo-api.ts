// Opt-in local API smoke. Creates fictional demo projects; never deletes history.
// NEXT_PUBLIC_API_URL=http://127.0.0.1:8858 NEXT_PUBLIC_API_KEY=demo-key node --experimental-strip-types scripts/check-demo-api.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { listZipEntries } from "../lib/zip.ts";
import { matchRequirement } from "../lib/docmatch.ts";
const storage = new Map<string, string>();
Object.assign(globalThis, { window: { localStorage: {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
} } });
const b = await import("../lib/backend.ts");
assert.equal(process.env.NEXT_PUBLIC_API_URL, "http://127.0.0.1:8858", "Only the isolated demo API is allowed");
const lookup = await b.permitLookup(); assert.ok(lookup); assert.equal(lookup.requirements.length, 10);
const [first, same] = await Promise.all([b.ensureProject(), b.ensureProject()]); assert.ok(first); assert.equal(first.id, same?.id);
let project = first;
for (const [zip, count] of [
  ["clearpath-demo-1-application.zip", 3], ["clearpath-demo-2-plans-and-forms.zip", 7],
  ["clearpath-demo-3-final.zip", 10], ["clearpath-demo-all.zip", 10],
] as const) {
  const data = readFileSync(new URL(`../public/demo/${zip}`, import.meta.url));
  const names = listZipEntries(data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength) as ArrayBuffer);
  for (const name of names) {
    const key = matchRequirement(name, lookup.requirements);
    if (name === "Site_Photos.pdf") assert.equal(key, null);
    if (!key) continue;
    const updated = await b.markRequirementReady(project.id, key, project.revision);
    assert.ok(updated, `PATCH ${key}`); project = updated;
  }
  const saved = await b.getProject(project.id); assert.ok(saved);
  assert.equal(saved.checklist.filter(c => c.status === "ready").length, count);
  assert.equal(saved.checklist.filter(c => c.applicability === "needs_information").length, 2);
  console.log(`PASS ${zip}: ${count}/10 saved; 2 applicability Unknown items preserved`);
}
const timeline = await b.loadDemoTimeline(new Date().toISOString().slice(0, 10));
assert.equal(timeline?.project_id, project.id); console.log("PASS Timeline uses the receipt project");
// Force a real optimistic-lock conflict and verify the client's refetch/retry.
assert.ok(await b.markRequirementReady(project.id, "covenant", 1));
console.log("PASS real API 409 refetch/retry");
b.clearStoredProjectId();
const fresh = await b.ensureProject(); assert.ok(fresh); assert.notEqual(fresh.id, project.id);
assert.equal(fresh.checklist.filter(c => c.status === "ready").length, 0);
assert.equal((await b.getProject(project.id))?.checklist.filter(c => c.status === "ready").length, 10);
console.log("PASS reset creates a fresh project and preserves old receipt history");
console.log(`ALL OK: local API persistence; old=${project.id}; fresh=${fresh.id}`);
