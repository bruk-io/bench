/** The projects route's edge: the disk, on the server that is already serving the page.
 *
 * Everything that can be decided from the request alone is decided in `src/route.ts`; this is
 * what is left, and all of it is I/O - where the root is, what a name resolves to once every
 * symlink is followed, what is on disk now, and the reads and writes themselves. Registered by
 * `vite.config.ts` in both `configureServer` and `configurePreviewServer`, so `npm run dev`,
 * `npm run preview` and therefore `tools/preview.py` all answer it.
 *
 * **Where it sits matters.** A middleware a plugin adds in either hook runs *ahead of* Vite's
 * own host check and CORS handling - Vite pushes those onto the stack after the hooks return
 * (vite 6.4, `_createServer` and `preview` in `dep-*.js`). So `server.allowedHosts` and
 * `preview.allowedHosts` protect the rest of the app and not this route, and the route keeps
 * the same host rule itself (`hostRefused`).
 *
 * **A version is a hash of the bytes, not the modification time.** A read carries the mtime
 * too, because that is what a person is shown, but a write is checked against a SHA-256 of
 * the content it was made from. mtime is one to two seconds coarse on FAT, exFAT, SMB and
 * HFS+, and the common edit here - a knob turned from 4 to 5 - changes nothing's size, so
 * mtime and size together would wave through exactly the race decision-9 names: the maker's
 * editor saving inside the same second as the app. Hashing costs a read of the file at each
 * write, which for a script or a values document is nothing and for a mesh is milliseconds.
 *
 * **What is not closed**: the check and the write are two steps. Between hashing the file and
 * renaming the new bytes over it, another program can still write it, and that write is
 * lost. The window is the time a rename takes; closing it needs a lock every writer honours,
 * and `vim` honours none.
 */
import { createHash, randomBytes } from "node:crypto";
import { mkdirSync } from "node:fs";
import { type FileHandle, link, lstat, mkdir, open, readFile, readdir, realpath, rename, stat, unlink } from "node:fs/promises";
import type { IncomingMessage, ServerResponse } from "node:http";
import { dirname, isAbsolute, join, resolve, sep } from "node:path";
import type { TLSSocket } from "node:tls";
import { fileURLToPath } from "node:url";

import {
  type AllowedHosts,
  type Operation,
  type Refusal,
  MAX_BODY,
  decided,
  refusal,
  within,
} from "../src/route";

/** The one environment variable that says where the projects are. `tools/projects.py` reads
 * the same one, with the same default and the same refusal of a relative path. */
export const VARIABLE = "BENCH_PROJECTS";

/** Where the projects are when nobody says: `projects/` at the top of the repository,
 * gitignored. A directory of the repository's own rather than a refusal to start, because
 * `npm run dev` with nothing set is how everybody starts, and a route that is not there is a
 * bench that cannot open anything; and inside the repository rather than somewhere in the
 * home directory, so a checkout that is deleted takes what it made with it. */
export const DEFAULT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "projects");

/** The projects root `env` designates, and whether it is the default.
 *
 * Unset and empty both mean the default. A relative path is refused rather than resolved,
 * because Vite runs from `web/` and `tools.build` from wherever it is started, and the two
 * would resolve it against different directories - the one disagreement AC#1 exists to rule
 * out.
 *
 * Raises:
 *     Error: if the variable holds a relative path.
 */
export function projectsRoot(env: Readonly<Record<string, string | undefined>>): {
  readonly root: string;
  readonly fallback: boolean;
} {
  const said = env[VARIABLE];
  if (said === undefined || said === "") return { root: DEFAULT, fallback: true };
  if (!isAbsolute(said)) {
    throw new Error(`${VARIABLE} must be an absolute path, and is "${said}"`);
  }
  return { root: resolve(said), fallback: false };
}

/** The root for this server, made if it is the default and not there yet. A root somebody
 * *named* is never made: a typo in a path is reported as a missing root on the first request,
 * rather than turned into a fresh empty directory on their disk. */
export function rootFor(env: Readonly<Record<string, string | undefined>>): string {
  const { root, fallback } = projectsRoot(env);
  if (fallback) mkdirSync(root, { recursive: true });
  return root;
}

/** An answer: a status, headers and a body. */
interface Answer {
  readonly status: number;
  readonly headers: Readonly<Record<string, string>>;
  readonly body: string | Uint8Array;
}

const json = (status: number, value: unknown, headers: Record<string, string> = {}): Answer => ({
  status,
  headers: { "content-type": "application/json", ...headers },
  body: JSON.stringify(value),
});

const refused = (found: Refusal): Answer => json(found.status, found);

/** A file's version: what a write names in `If-Match` and a read hands out as its `ETag`. */
const versionOf = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex");

/** What a read or a write says about the file it leaves behind. */
interface Version {
  readonly version: string;
  readonly mtimeMs: number;
  readonly size: number;
}

const versionHeaders = (found: Version): Record<string, string> => ({
  etag: `"${found.version}"`,
  "x-bench-mtime": String(found.mtimeMs),
  "x-bench-size": String(found.size),
});

async function versioned(path: string): Promise<Version> {
  const bytes = await readFile(path);
  const info = await stat(path);
  return { version: versionOf(bytes), mtimeMs: info.mtimeMs, size: info.size };
}

const code = (error: unknown): string | undefined =>
  typeof error === "object" && error !== null && "code" in error ? String(error.code) : undefined;

/** `path` with every symlink followed, or `null` if there is nothing there. */
async function real(path: string): Promise<string | null> {
  try {
    return await realpath(path);
  } catch (error) {
    if (code(error) === "ENOENT" || code(error) === "ENOTDIR") return null;
    throw error;
  }
}

/** The root, resolved - or a refusal if it is not a directory that exists. */
async function realRoot(root: string): Promise<string | Refusal> {
  const found = await real(root);
  if (found === null || !(await stat(found)).isDirectory()) {
    return refusal("no-root", `there is no projects directory at ${root}`);
  }
  return found;
}

/** A project's directory, resolved, and checked to be inside the root; made first when
 * `make` is set and it is not there, since a new file is how a new project begins. */
async function projectDir(rootReal: string, project: string, make = false): Promise<string | Refusal> {
  const path = join(rootReal, project);
  let found = await real(path);
  if (found === null && make) {
    // Not recursive: the root exists, so the only directory this can make is the project's.
    try {
      await mkdir(path);
    } catch (error) {
      if (code(error) !== "EEXIST") throw error;
    }
    found = await real(path);
  }
  if (found === null) return refusal("missing", `there is no project called ${project}`);
  if (!within(rootReal, found, sep)) {
    return refusal("outside", `${project} leads outside the projects directory`);
  }
  if (!(await stat(found)).isDirectory()) return refusal("missing", `${project} is not a project`);
  return found;
}

/** A file in a project, to be read: followed through any symlink as long as where it lands
 * is still inside the root. */
async function readable(rootReal: string, dir: string, at: string, file: string): Promise<string | Refusal> {
  const found = await real(join(dir, file));
  if (found === null) return refusal("missing", `there is no ${at}`, at);
  if (!within(rootReal, found, sep)) return refusal("outside", `${at} leads outside the projects directory`, at);
  if (!(await stat(found)).isFile()) return refusal("missing", `${at} is not a file`, at);
  return found;
}

/** A file in a project, to be changed: the entry itself must be a plain file. A symlink is
 * refused whatever it points at - writing through one changes a file somewhere the maker did
 * not name, and renaming or deleting one does something different from what the row says. */
async function changeable(dir: string, at: string, file: string): Promise<string | Refusal> {
  const path = join(dir, file);
  let info;
  try {
    info = await lstat(path);
  } catch (error) {
    if (code(error) === "ENOENT") return refusal("missing", `there is no ${at}`, at);
    throw error;
  }
  if (info.isSymbolicLink()) {
    return refusal("link", `${at} is a symbolic link, and the route does not change one`, at);
  }
  if (!info.isFile()) return refusal("missing", `${at} is not a file`, at);
  return path;
}

/** The whole body, or `null` if it went past `MAX_BODY` - read to the end either way, so the
 * client is not cut off mid-send and gets the answer instead of a reset. */
async function body(req: IncomingMessage): Promise<Uint8Array | null> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req as AsyncIterable<Buffer>) {
    size += chunk.length;
    if (size <= MAX_BODY) chunks.push(chunk);
  }
  return size > MAX_BODY ? null : Buffer.concat(chunks);
}

const isRefusal = (found: unknown): found is Refusal =>
  typeof found === "object" && found !== null && "refused" in found;

/** Write `bytes` beside `path` under a hidden name, then rename it over `path`, so nothing
 * reading the file - `tools.build`, the maker's editor - ever sees half of it. */
async function replaced(path: string, bytes: Uint8Array): Promise<void> {
  const staged = join(dirname(path), `.${randomBytes(6).toString("hex")}.bench-write`);
  let handle: FileHandle | null = await open(staged, "wx");
  try {
    await handle.writeFile(bytes);
    await handle.close();
    handle = null;
    await rename(staged, path);
  } catch (error) {
    await handle?.close();
    await unlink(staged).catch(() => undefined);
    throw error;
  }
}

/** Do `operation` against the root, and say how it went. */
async function performed(root: string, operation: Operation, req: IncomingMessage): Promise<Answer> {
  const rootReal = await realRoot(root);
  if (isRefusal(rootReal)) return refused(rootReal);

  if (operation.op === "projects") {
    const projects: string[] = [];
    for (const entry of await readdir(rootReal, { withFileTypes: true })) {
      if (entry.name.startsWith(".")) continue;
      const found = await real(join(rootReal, entry.name));
      if (found === null || !within(rootReal, found, sep)) continue;
      if ((await stat(found)).isDirectory()) projects.push(entry.name);
    }
    return json(200, { root: rootReal, projects: projects.sort() });
  }

  const dir = await projectDir(rootReal, operation.project, operation.op === "create");
  if (isRefusal(dir)) return refused(dir);

  if (operation.op === "files") {
    const files: { name: string; mtimeMs: number; size: number }[] = [];
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      if (entry.name.startsWith(".")) continue;
      const found = await real(join(dir, entry.name));
      if (found === null || !within(rootReal, found, sep)) continue;
      const info = await stat(found);
      if (info.isFile()) files.push({ name: entry.name, mtimeMs: info.mtimeMs, size: info.size });
    }
    files.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    return json(200, { project: operation.project, files });
  }

  const at = `${operation.project}/${operation.file}`;

  if (operation.op === "read") {
    const path = await readable(rootReal, dir, at, operation.file);
    if (isRefusal(path)) return refused(path);
    const bytes = await readFile(path);
    const info = await stat(path);
    const found = { version: versionOf(bytes), mtimeMs: info.mtimeMs, size: info.size };
    return {
      status: 200,
      headers: { "content-type": "application/octet-stream", ...versionHeaders(found) },
      body: bytes,
    };
  }

  if (operation.op === "create") {
    const bytes = await body(req);
    if (bytes === null) return refused(refusal("too-large", `${at} is too large to write`, at));
    const path = join(dir, operation.file);
    let handle: FileHandle;
    try {
      // O_EXCL: fails on anything already there, a dangling symlink included, and never
      // follows one - the check and the create are one step.
      handle = await open(path, "wx");
    } catch (error) {
      if (code(error) === "EEXIST") return refused(refusal("exists", `${at} is already there`, at));
      throw error;
    }
    try {
      await handle.writeFile(bytes);
    } finally {
      await handle.close();
    }
    const found = await versioned(path);
    return json(201, found, versionHeaders(found));
  }

  const path = await changeable(dir, at, operation.file);
  if (isRefusal(path)) return refused(path);

  if (operation.op === "rename") {
    const to = `${operation.project}/${operation.to}`;
    const target = join(dir, operation.to);
    try {
      // A hard link fails if the name is taken, where a rename would replace it - so this is
      // the check and the move in one step, and the old name goes only once the new one is.
      await link(path, target);
    } catch (error) {
      if (code(error) !== "EEXIST") throw error;
      // On a case-insensitive disk `Cabinet.py` is `cabinet.py`: the same file, not a clash.
      const [from, onto] = await Promise.all([stat(path), stat(target)]);
      if (from.ino !== onto.ino || from.dev !== onto.dev) {
        return refused(refusal("exists", `${to} is already there`, to));
      }
      await rename(path, target);
      return json(200, await versioned(target));
    }
    await unlink(path);
    return json(200, await versioned(target));
  }

  // A write or a delete: both only if the file is still what the client last saw.
  const current = versionOf(await readFile(path));
  if (current !== operation.base) {
    return refused(refusal("moved", `${at} has changed on disk since it was read`, at));
  }

  if (operation.op === "delete") {
    // Plain unlink for now. task-48 makes a delete recoverable - a move to a trash directory
    // under the root - at the level the person sees it.
    await unlink(path);
    return { status: 204, headers: {}, body: "" };
  }

  const bytes = await body(req);
  if (bytes === null) return refused(refusal("too-large", `${at} is too large to write`, at));
  await replaced(path, bytes);
  const found = await versioned(path);
  return json(200, found, versionHeaders(found));
}

/** The middleware: `/__bench/projects/…` answered against `root`, everything else passed on.
 * `allowed` is the server's own `allowedHosts` - dev's or preview's, whichever this is. */
export function projectsRoute(
  root: string,
  allowed: AllowedHosts,
): (req: IncomingMessage, res: ServerResponse, next: () => void) => void {
  return (req, res, next) => {
    const header = (name: string): string | undefined => {
      const found = req.headers[name];
      return Array.isArray(found) ? found.join(", ") : found;
    };
    const operation = decided(
      {
        method: req.method ?? "GET",
        url: req.url ?? "/",
        scheme: (req.socket as TLSSocket).encrypted ? "https" : "http",
        host: header("host"),
        origin: header("origin"),
        fetchSite: header("sec-fetch-site"),
        ifMatch: header("if-match"),
        ifNoneMatch: header("if-none-match"),
      },
      allowed,
    );
    if (operation === null) {
      next();
      return;
    }
    const answered = isRefusal(operation) ? Promise.resolve(refused(operation)) : performed(root, operation, req);
    answered
      .catch((error: unknown) => refused(refusal("failed", String(error))))
      .then((answer) => {
        res.statusCode = answer.status;
        res.setHeader("cache-control", "no-store");
        for (const [name, value] of Object.entries(answer.headers)) res.setHeader(name, value);
        res.end(answer.body);
      })
      .catch(() => {
        // The client went away mid-answer; there is nobody left to tell.
      });
  };
}
