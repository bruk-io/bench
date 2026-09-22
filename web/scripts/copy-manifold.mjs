// Copy Manifold's WASM build out of node_modules so the app serves it itself.
// The twin of copy-pyodide.mjs, and for the same reason: the worker loads the solid
// modeller from `<base>/manifold/`, and nothing is fetched from a CDN at run time.
//
// Two files, not one. `manifold.wasm` is the modeller; `manifold.js` is the emscripten glue
// that instantiates it, and it is imported by URL rather than bundled so the pair stays
// together and the worker chunk stays small - `locateFile` is what points the glue at the
// copy beside it.
//
// Like copy-pyodide.mjs, each copy keeps the package's modification time, so a rebuild does
// not hand a browser that has the modeller cached a new ETag for the same bytes.
import { copyFile, mkdir, stat, utimes } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = dirname(HERE);
const FROM = join(WEB, "node_modules", "manifold-3d");
const INTO = join(WEB, "public", "manifold");

const FILES = ["manifold.js", "manifold.wasm"];

await mkdir(INTO, { recursive: true });
for (const name of FILES) {
  const from = join(FROM, name);
  const info = await stat(from).catch(() => null);
  if (info === null) {
    console.error(`copy-manifold: missing ${from} - run npm install`);
    process.exit(1);
  }
  await copyFile(from, join(INTO, name));
  await utimes(join(INTO, name), info.atime, info.mtime);
  console.log(`copy-manifold: ${name} (${(info.size / 1024).toFixed(0)} kB)`);
}
