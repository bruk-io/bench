// Give the runtime files in dist/ the timestamps of the packages they came from.
//
// A static server tells a browser whether its cached copy is still good with an ETag, and
// the one `vite preview` sends is the file's size and modification time. Vite copies public/
// into dist/ afresh on every build, so every build gave thirteen megabytes of unchanged
// runtime a new ETag, and every browser that already had it - a tablet on the same network,
// say - downloaded all of it again. With this, the ETag changes when the runtime does, which
// is a new Pyodide or Manifold release, and not before.
//
// The copy scripts keep the package's timestamp on the public/ copy; this carries it on to
// the dist/ copy, which is the one that is served.
import { readdir, stat, utimes } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = dirname(dirname(fileURLToPath(import.meta.url)));
const RUNTIMES = ["pyodide", "manifold"];

for (const runtime of RUNTIMES) {
  const built = join(WEB, "dist", runtime);
  const names = await readdir(built).catch(() => null);
  if (names === null) {
    console.error(`keep-runtime-times: no ${built} - run the build first`);
    process.exit(1);
  }
  for (const name of names) {
    const source = await stat(join(WEB, "public", runtime, name));
    await utimes(join(built, name), source.atime, source.mtime);
  }
  console.log(`keep-runtime-times: ${runtime} (${names.length} files)`);
}
