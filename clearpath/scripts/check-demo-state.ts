// Run: node --experimental-strip-types scripts/check-demo-state.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { listZipEntries } from "../lib/zip.ts";

process.env.NEXT_PUBLIC_API_URL = "http://demo.test";
process.env.NEXT_PUBLIC_API_KEY = "test-only";
const storage = new Map<string, string>();
Object.assign(globalThis, { window: { localStorage: {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
} } });
const backend = await import("../lib/backend.ts");
let failures = 0;
async function check(name: string, run: () => unknown) {
  try { await run(); console.log(`PASS ${name}`); }
  catch (error) { failures++; console.error(`FAIL ${name}: ${error}`); }
}
const bytes = readFileSync(new URL("../public/demo/clearpath-demo-1-application.zip", import.meta.url));
const archive = () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
await check("empty and malformed ZIP reject visibly", () => {
  assert.throws(() => listZipEntries(new ArrayBuffer(0)), /ZIP/i);
  assert.throws(() => listZipEntries(new ArrayBuffer(24)), /ZIP/i);
});
await check("truncated central directory and names reject", () => {
  const buf = archive(); const view = new DataView(buf);
  const end = buf.byteLength - 22;
  view.setUint32(end + 16, buf.byteLength - 1, true);
  assert.throws(() => listZipEntries(buf), /ZIP/i);
  const badName = archive(); const v = new DataView(badName);
  const start = v.getUint32(badName.byteLength - 6, true);
  v.setUint16(start + 28, 65535, true);
  assert.throws(() => listZipEntries(badName), /ZIP/i);
});
await check("concurrent init and Timeline share one project", async () => {
  backend.clearStoredProjectId(); let creates = 0;
  globalThis.fetch = async (url, options) => {
    const path = String(url);
    if (options?.method === "POST" && path.endsWith("/projects")) { creates++; await new Promise(r => setTimeout(r, 5)); }
    return Response.json(path.endsWith("/timeline") ? { project_id: "shared" } : { id: "shared", revision: 1, checklist: [] });
  };
  const [a, b, timeline] = await Promise.all([backend.ensureProject(), backend.ensureProject(), backend.loadDemoTimeline()]);
  assert.equal(creates, 1); assert.equal(a?.id, b?.id); assert.equal(timeline?.project_id, a?.id);
});
await check("reset invalidates pending initialization", async () => {
  backend.clearStoredProjectId(); let release!: () => void;
  const gate = new Promise<void>(r => { release = r; });
  globalThis.fetch = async () => { await gate; return Response.json({ id: "obsolete", revision: 1, checklist: [] }); };
  const pending = backend.ensureProject(); backend.clearStoredProjectId(); release();
  assert.equal(await pending, null); assert.equal(backend.readStoredProjectId(), null);
});
await check("network failure does not replace existing identity", async () => {
  backend.clearStoredProjectId(); storage.set(backend.PROJECT_KEY, "existing"); let posts = 0;
  globalThis.fetch = async (_url, options) => { if (options?.method === "POST") posts++; throw new Error("offline"); };
  assert.equal(await backend.ensureProject(), null); assert.equal(posts, 0); assert.equal(backend.readStoredProjectId(), "existing");
});
await check("409 refetches revision and retries once; other errors do not", async () => {
  const revisions: number[] = []; let patches = 0;
  globalThis.fetch = async (_url, options) => {
    if (options?.method === "PATCH") {
      revisions.push(JSON.parse(String(options.body)).expected_revision);
      return ++patches === 1 ? new Response("{}", { status: 409 }) : Response.json({ project: { id: "shared", revision: 4, checklist: [] } });
    }
    return Response.json({ id: "shared", revision: 3, checklist: [] });
  };
  assert.equal((await backend.markRequirementReady("shared", "adu-permit-application", 1))?.revision, 4);
  assert.deepEqual(revisions, [1, 3]);
  let calls = 0; globalThis.fetch = async () => { calls++; return new Response("{}", { status: 503 }); };
  assert.equal(await backend.markRequirementReady("shared", "covenant", 4), null); assert.equal(calls, 1);
});
await check("receipt storage is scoped, validated, and reset independently", async () => {
  const { loadReceipts, saveReceipts, clearReceipts } = await import("../lib/receipts.ts");
  storage.set("clearpath.receivedDocs", JSON.stringify({ covenant: "legacy.pdf" }));
  assert.deepEqual(loadReceipts("new-project"), { files: {}, unsaved: [] });
  saveReceipts("one", { files: { covenant: "Covenant.pdf" }, unsaved: ["covenant"] });
  assert.deepEqual(loadReceipts("two"), { files: {}, unsaved: [] });
  assert.deepEqual(loadReceipts("one").unsaved, ["covenant"]);
  clearReceipts("one"); assert.deepEqual(loadReceipts("one"), { files: {}, unsaved: [] });
  storage.set("clearpath.receivedDocs:broken", "{");
  assert.deepEqual(loadReceipts("broken"), { files: {}, unsaved: [] });
});
console.log(failures ? `FAILED: ${failures} regressions` : "ALL OK: ZIP bounds and shared project lifecycle regressions");
process.exitCode = failures ? 1 : 0;
