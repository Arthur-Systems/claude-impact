// Lists names only. Never extracts files or validates document contents.
export function listZipEntries(buf: ArrayBuffer): string[] {
  const invalid = () => new Error("Invalid, empty, truncated, or unsupported ZIP. Choose a standard ZIP containing files.");
  const view = new DataView(buf);
  const len = buf.byteLength;
  let eocd = -1;
  for (let i = len - 22; i >= Math.max(0, len - 65557); i--) {
    if (view.getUint32(i, true) === 0x06054b50 && i + 22 + view.getUint16(i + 20, true) === len) { eocd = i; break; }
  }
  if (eocd < 0) throw invalid();
  const count = view.getUint16(eocd + 10, true);
  const size = view.getUint32(eocd + 12, true);
  let p = view.getUint32(eocd + 16, true);
  const end = p + size;
  if (!count || count === 65535 || view.getUint16(eocd + 4, true) || view.getUint16(eocd + 6, true) ||
      view.getUint16(eocd + 8, true) !== count || end > eocd || size < count * 46) throw invalid();
  const dec = new TextDecoder("utf-8");
  const out: string[] = [];
  for (let n = 0; n < count; n++) {
    if (p + 46 > end || view.getUint32(p, true) !== 0x02014b50) throw invalid();
    const nameLen = view.getUint16(p + 28, true);
    const next = p + 46 + nameLen + view.getUint16(p + 30, true) + view.getUint16(p + 32, true);
    if (!nameLen || next > end || view.getUint32(p + 42, true) >= p) throw invalid();
    const name = dec.decode(new Uint8Array(buf, p + 46, nameLen));
    if (name.includes("\u0000")) throw invalid();
    p = next;
    if (name.endsWith("/") || name.startsWith("__MACOSX/")) continue;
    const base = name.split(/[\\/]/).pop() ?? name;
    if (base && !base.startsWith(".")) out.push(base);
  }
  if (p !== end || !out.length) throw invalid();
  return out;
}
