// Browser receipt metadata only, isolated by API project identity. No document bytes.
export type Receipts = { files: Record<string, string>; unsaved: string[] };
const keyFor = (projectId: string) => `clearpath.receivedDocs:${projectId}`;
export function loadReceipts(projectId: string): Receipts {
  try {
    const value = JSON.parse(window.localStorage.getItem(keyFor(projectId)) || "null");
    const files: Record<string, string> = {};
    if (value?.files && typeof value.files === "object") {
      for (const [key, name] of Object.entries(value.files)) if (typeof name === "string") files[key] = name;
    }
    return { files, unsaved: Array.isArray(value?.unsaved) ? value.unsaved.filter((key: unknown) => typeof key === "string" && key in files) : [] };
  } catch { return { files: {}, unsaved: [] }; }
}
export function saveReceipts(projectId: string, receipts: Receipts) {
  try { window.localStorage.setItem(keyFor(projectId), JSON.stringify(receipts)); } catch {}
}
export function clearReceipts(projectId: string) {
  try { window.localStorage.removeItem(keyFor(projectId)); } catch {}
}
