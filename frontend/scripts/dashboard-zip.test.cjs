const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
// Load actual TS modules, stubbing React only to inspect provider updates without a browser.
function load(file, state = []) {
  const ts = require('typescript');
  const full = path.resolve(__dirname, '../lib', file);
  const mod = { exports: {} };
  const react = { createContext: () => ({ Provider: 'provider' }), useContext: () => {}, useMemo: f => f(), useState: initial => [Array.isArray(initial) ? state : initial, f => { state.splice(0, state.length, ...f(state)); }] };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(full, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, {
    module: mod, exports: mod.exports, crypto: require('node:crypto').webcrypto, TextDecoder, DataView, Uint8Array,
    require: name => name === 'react' ? react : name === 'react/jsx-runtime' ? { jsx: (_tag, props) => props } : load(name.replace('./', '') + (name.endsWith('.ts') ? '' : '.ts'), state),
  });
  return mod.exports;
}
const names = ['01_Site_Plan.pdf', '02_Floor_Plans.pdf', '03_Proof_of_Ownership.pdf', '04_Structural_Calculations.pdf', 'Holiday_Photo.pdf', '05_Energy_Compliance_Report.pdf', '06_Elevations.pdf'];
test('actual provider rejects site photos and deduplicates names', () => {
  const state = [];
  const { ProjectProvider } = load('project-context.tsx', state);
  const ctx = ProjectProvider({ children: null }).value;
  ctx.addFiles(['Site_Photos.pdf']);
  assert.equal(state[0].matchedTo, null);
  ctx.addFiles(['SITE_PHOTOS.PDF']);
  assert.equal(state.length, 1);
  ctx.removeFile(state[0].id);
  assert.equal(state.length, 0);
  for (const [pack, expected] of [[names.slice(0, 2), 2], [names.slice(2, 5), 4], [names.slice(5), 6]]) {
    ctx.addFiles(pack);
    assert.equal(new Set(state.map(f => f.matchedTo).filter(Boolean)).size, expected);
  }
  ctx.addFiles(names.map(n => n.toUpperCase()));
  assert.equal(state.length, 7);
  const holiday = state.find(f => f.name === 'Holiday_Photo.pdf');
  ctx.reassign(holiday.id, 'site');
  assert.equal(state.find(f => f.id === holiday.id).matchedTo, 'site');
  ctx.reassign(holiday.id, null);
  assert.equal(state.find(f => f.id === holiday.id).matchedTo, null);
  for (const file of [...state]) ctx.removeFile(file.id);
  assert.equal(state.length, 0);
});
test('component wires ZIP input, busy guard and visible errors', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '../components/DocumentsCard.tsx'), 'utf8');
  assert.match(source, /accept="[^"]*\.zip/);
  assert.match(source, /busyRef\.current = true/);
  assert.match(source, /finally/);
  assert.match(source, /role="alert"/);
  assert.ok(source.indexOf('busyRef.current = true') < source.indexOf('await expandUpload'));
  assert.match(source, /addFiles\(\[name\]\)/);
  assert.match(source, /setTimeout\(resolve, 300\)/);
  assert.equal((source.match(/disabled=\{busy\}/g) || []).length, 3);
});
test('real pure matching, dedupe and staged ZIP expansion', async () => {
  const { guessMatch, uniqueNames, expandUpload } = load('document-files.ts');
  assert.deepEqual(Array.from(names, n => guessMatch(n).matchedTo), ['site','floor','ownership','structural',null,'energy','elevations']);
  for (const name of ['Site_Plan.pdf','Site-Plan.pdf','Site Plan.pdf','siteplan.pdf']) assert.equal(guessMatch(name).matchedTo, 'site');
  assert.equal(guessMatch('Site_Photos.pdf').matchedTo, null);
  assert.equal(guessMatch('Title24.pdf').matchedTo, 'energy');
  assert.equal(uniqueNames(['a.pdf'], ['A.PDF', 'b.pdf', 'B.pdf']).length, 1);
  await assert.rejects(expandUpload({ name: 'bad.zip', arrayBuffer: async () => new ArrayBuffer(5) }), /ZIP/);
  assert.deepEqual(Array.from(await expandUpload({ name: 'Site_Plan.pdf', arrayBuffer: async () => { throw new Error('PDF contents must not be read'); } })), ['Site_Plan.pdf']);
  let accumulated = [];
  for (const [suffix, count] of [['1-plans',2], ['2-supporting',4], ['3-final',6], ['all',6]]) {
    const bytes = fs.readFileSync(path.resolve(__dirname, `../public/demo/clearpath-dashboard-${suffix}.zip`));
    const entries = await expandUpload({ name: 'sample.zip', arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) });
    await assert.rejects(expandUpload({ name: 'truncated.zip', arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength - 1) }), /ZIP/);
    accumulated.push(...uniqueNames(accumulated, entries));
    assert.equal(new Set(accumulated.map(n => guessMatch(n).matchedTo).filter(Boolean)).size, count);
  }
  assert.deepEqual(accumulated, names);
});
