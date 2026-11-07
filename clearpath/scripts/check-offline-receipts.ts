// Exercises the actual Documents initialization effect, without a DOM or network.
// Run: node --experimental-strip-types scripts/check-offline-receipts.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import * as receipts from "../lib/receipts.ts";
const require = createRequire(import.meta.url);
const ts = require("typescript");
const source = readFileSync(new URL("../app/documents/page.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020,
} }).outputText;
const projectId = "offline-regression-project";
const storageKey = `clearpath.receivedDocs:${projectId}`;
const keys = ["adu-permit-application", "adu-verification-form", "address-application"];
const original = JSON.stringify({ files: Object.fromEntries(keys.map((key, index) => [key, `fictional-${index}.pdf`])), unsaved: keys });
const storage = new Map<string, string>([[storageKey, original]]);
let writes = 0;
Object.assign(globalThis, { window: { localStorage: {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => { writes++; storage.set(key, value); },
  removeItem: (key: string) => storage.delete(key),
} } });
async function initialize(lookup: unknown, project: unknown) {
  const effects: (() => unknown)[] = [];
  const states: unknown[] = [];
  const modules: Record<string, unknown> = {
    react: {
      useRef: (current: unknown) => ({ current }),
      useState: (initial: unknown) => { const index = states.length; states.push(initial); return [initial, (value: unknown) => { states[index] = value; }]; },
      useEffect: (effect: () => unknown) => effects.push(effect),
    },
    "react/jsx-runtime": { jsx: () => null, jsxs: () => null, Fragment: "fragment" },
    "@/components/PageHeader": { default: () => null },
    "@/components/LiveData": {},
    "@/lib/backend": {
      backendConfigured: () => true, permitLookup: async () => lookup,
      ensureProject: async () => project, readStoredProjectId: () => projectId,
    },
    "@/lib/project-context": { REQUIRED_DOCS: [], useProject: () => ({ files: [], missingPriority: [], unmatched: [] }) },
    "@/lib/zip": {}, "@/lib/docmatch": {}, "@/lib/receipts": receipts,
  };
  const exports: { default?: () => unknown } = {};
  runInNewContext(compiled, { exports, require: (name: string) => {
    assert.ok(name in modules, `Unexpected production import: ${name}`); return modules[name];
  }, setTimeout });
  exports.default!();
  assert.equal(effects.length, 1);
  effects[0]();
  await new Promise<void>(resolve => setImmediate(resolve));
  return states;
}
let failures = 0;
for (const [name, run] of [
  ["offline init preserves project receipts byte-for-byte without writes", async () => {
    const states = await initialize(null, null);
    assert.equal(storage.get(storageKey), original);
    assert.equal(writes, 0);
    assert.equal(states[1], null); assert.equal(states[2], false);
  }],
  ["failed lookup does not reconcile even when project fetch succeeds", async () => {
    storage.set(storageKey, original); writes = 0;
    const states = await initialize(null, { id: projectId, revision: 2, checklist: [] });
    assert.equal(storage.get(storageKey), original); assert.equal(writes, 0); assert.equal(states[2], false);
  }],
  ["online init recovers three receipts and warns for two unsaved files", async () => {
    // Use the bytes left by offline initialization, not a replacement fixture.
    const states = await initialize({ requirements: keys.map(key => ({ key })) }, {
      id: projectId, revision: 3, checklist: [{ key: keys[0], status: "ready" }],
    });
    assert.deepEqual(Object.keys(states[3] as object).sort(), [...keys].sort());
    assert.equal(states[6], true); assert.equal(states[2], false);
    assert.deepEqual(receipts.loadReceipts(projectId).unsaved, keys.slice(1));
  }],
] as const) {
  try { await run(); console.log(`PASS ${name}`); }
  catch (error) { failures++; console.error(`FAIL ${name}: ${error}`); }
}
console.log(failures ? `FAILED: ${failures} offline initialization regressions` : "ALL OK: offline initialization retention and online recovery");
process.exitCode = failures ? 1 : 0;
