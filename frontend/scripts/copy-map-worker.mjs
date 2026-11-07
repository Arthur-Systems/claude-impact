import { copyFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Serve the installed module worker unchanged, outside Next's asset minifier.
// npm runs this on every dev/build, including after a clean npm ci.
const require = createRequire(import.meta.url);
const source = dirname(require.resolve("maplibre-gl/package.json"));
const target = fileURLToPath(new URL("../public/maplibre/", import.meta.url));
await mkdir(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-worker.mjs.map"]) {
  await copyFile(join(source, "dist", file), join(target, file));
}
await copyFile(join(source, "LICENSE.txt"), join(target, "LICENSE.txt"));
