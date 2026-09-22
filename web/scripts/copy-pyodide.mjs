// Copy the Pyodide runtime out of node_modules so the app serves it itself.
// The npm package ships everything; nothing is fetched from a CDN at run time.
//
// Each copy keeps the package's own modification time. A server's ETag is made from it, so a
// fresh timestamp on every build would tell every browser that had the runtime cached to
// download all thirteen megabytes again - see keep-runtime-times.mjs for the dist/ half.
import { copyFile, mkdir, stat, utimes } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = dirname(HERE);
const FROM = join(WEB, "node_modules", "pyodide");
const INTO = join(WEB, "public", "pyodide");

const FILES = [
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
];

await mkdir(INTO, { recursive: true });
for (const name of FILES) {
  const from = join(FROM, name);
  const info = await stat(from).catch(() => null);
  if (info === null) {
    console.error(`copy-pyodide: missing ${from} - run npm install`);
    process.exit(1);
  }
  await copyFile(from, join(INTO, name));
  await utimes(join(INTO, name), info.atime, info.mtime);
  console.log(`copy-pyodide: ${name} (${(info.size / 1024).toFixed(0)} kB)`);
}
