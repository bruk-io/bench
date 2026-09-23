import { spawn } from "node:child_process";
import { readdir, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { IncomingMessage, ServerResponse } from "node:http";

import { type Plugin, defineConfig } from "vite";

import { projectsRoute, rootFor } from "./server/projects";

const HERE = dirname(fileURLToPath(import.meta.url));
const PY = resolve(HERE, "..", "src", "bench");
const EXAMPLES = resolve(HERE, "..", "examples");

/** Re-run `scripts/bundle-py.mjs` when the Python side changes, in dev only.
 *
 * `npm run dev` generates `src/generated/pysources.ts` once, at `predev`, and Vite then has
 * no reason to look at `../src/bench` ever again - it is outside the project root and not
 * imported by anything. Editing a Python module and reloading the page got the old bundle,
 * which is a confusing half hour. Watching the two source trees and regenerating closes
 * that: the write to the generated module is an ordinary change Vite already follows, so
 * HMR takes it from there.
 */
function regeneratePython(): Plugin {
  let running = false;
  let again = false;

  const generate = (): void => {
    if (running) {
      again = true;
      return;
    }
    running = true;
    const child = spawn(process.execPath, [join(HERE, "scripts", "bundle-py.mjs")], {
      cwd: HERE,
      stdio: "inherit",
    });
    child.on("close", () => {
      running = false;
      if (!again) return;
      again = false;
      generate();
    });
  };

  return {
    name: "bench:regenerate-python",
    apply: "serve",
    configureServer(server) {
      server.watcher.add([PY, EXAMPLES]);
      const touched = (path: string): void => {
        if (!path.endsWith(".py")) return;
        if (!path.startsWith(PY) && !path.startsWith(EXAMPLES)) return;
        server.config.logger.info(`bundle-py: ${path} changed, regenerating`);
        generate();
      };
      server.watcher.on("add", touched);
      server.watcher.on("change", touched);
      server.watcher.on("unlink", touched);
    },
  };
}

/** The route `staleness()` answers on, both in `npm run dev` and `npm run preview`. Kept
 * out of `base`, since the page fetches it as an absolute path regardless of `base: "./"`. */
const ENDPOINT = "/__bench/generated-at";

/** The latest mtime, in milliseconds, among the `.py` files under `dir` - the same number
 * `bundle-py.mjs` freezes into `pysources.ts` as `GENERATED_AT` when it runs. */
async function newest(dir: string): Promise<number> {
  let found = 0;
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (entry.name === "__pycache__" || entry.name.startsWith(".")) continue;
    const path = join(dir, entry.name);
    if (entry.isDirectory()) found = Math.max(found, await newest(path));
    else if (entry.name.endsWith(".py")) found = Math.max(found, (await stat(path)).mtimeMs);
  }
  return found;
}

/** Answer `ENDPOINT` with what is newest on disk right now, live off the two source trees -
 * never off `pysources.ts`, which is the thing being asked about. A static deploy has no
 * such process behind it, so the page's own fetch to this route fails there and the check
 * says nothing rather than guessing; `dev` and `preview` both run a real node process, so
 * both can answer honestly, which is the whole reason this is a server route and not a
 * number baked in at build time.
 */
function staleness(): Plugin {
  const middleware = (req: IncomingMessage, res: ServerResponse, next: () => void): void => {
    if (req.url !== ENDPOINT) {
      next();
      return;
    }
    Promise.all([newest(PY), newest(EXAMPLES)])
      .then(([py, examples]) => {
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify({ newest: Math.max(py, examples) }));
      })
      .catch((error: unknown) => {
        // A file can vanish between `readdir` and `stat` - exactly what a `git pull` does
        // while this server is running. Answering nothing here would hang `bundleStale()`
        // (it has no timeout) rather than let the check fall back to "can't tell".
        res.statusCode = 500;
        res.end(JSON.stringify({ error: String(error) }));
      });
  };
  return {
    name: "bench:staleness",
    configureServer(server) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware);
    },
  };
}

/** The host's projects, read and written over `/__bench/projects/…` - decision-9's route.
 *
 * Beside `staleness()` and registered the same way, in both hooks, so dev and preview (and
 * `tools/preview.py`, which spawns preview) answer it alike. The root is resolved when the
 * server is configured, not when this file is loaded: `vite build` loads it too, and has no
 * business making a directory. What the route does and refuses is `server/projects.ts` and
 * `src/route.ts`.
 */
function projects(): Plugin {
  return {
    name: "bench:projects",
    configureServer(server) {
      server.middlewares.use(projectsRoute(rootFor(process.env), server.config.server.allowedHosts));
    },
    configurePreviewServer(server) {
      server.middlewares.use(projectsRoute(rootFor(process.env), server.config.preview.allowedHosts));
    },
  };
}

// `base: "./"` so the built app works from any sub-path; the worker is an ES module
// because it dynamically imports the self-hosted pyodide.mjs.
export default defineConfig({
  base: "./",
  build: { target: "es2022" },
  worker: { format: "es" },
  plugins: [regeneratePython(), staleness(), projects()],
});
