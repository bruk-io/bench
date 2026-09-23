/** What the projects route will and will not do, decided from the request alone.
 *
 * decision-9 puts a person's projects on the host - one directory per project under a root
 * the host designates - and reaches them over `/__bench/projects/…` on the server that is
 * already serving the page. That route reads and writes files on somebody's machine, so what
 * it refuses is settled here, as data, before anything touches a disk: a request comes in as
 * its method, its raw URL and a few headers, and goes out as either an operation to perform
 * or a refusal saying why not. `server/projects.ts` is the edge that performs it; `host.ts`
 * is the client that asks. Both import the refusal vocabulary from here, so the two ends
 * cannot drift on what a reason is called.
 *
 * No DOM and no `node:` imports: this module is loaded by `vite.config.ts` in Node and by the
 * page in a browser, and is tested in the second.
 *
 * **A path is a project and a file, checked - never a string joined onto the root.** The URL
 * is split on literal `/` *before* anything is decoded, then each segment is decoded once and
 * has to be a plain name: not empty, not `.` or `..`, no separator of either kind, no NUL or
 * other control character, and not hidden. That rules out `..`, `%2e%2e`, `%2F`, `//abs` and
 * a smuggled absolute path by construction rather than by pattern. `new URL()` is exactly the
 * wrong tool: it collapses dot segments, so a check built on it never sees the traversal it
 * is meant to refuse. What a *symlink* resolves to is a question only the disk can answer,
 * and the edge asks it with `within` below.
 *
 * **Who may write** is the one thing the request alone cannot settle: a project's write lease
 * (`lease.ts`) is held in the server's memory. So every operation that changes a project
 * carries the holder id it was sent as, and the edge checks it against the leases before it
 * touches the disk; the leases themselves are asked for under `LEASES`, decided here the same
 * way - one plain name, the same host and origin rules.
 */

import { ACTS, type Act, holderProblem } from "./lease";

/** Where the route answers - beside `/__bench/generated-at`, and like it kept out of `base`,
 * since the page asks for it as an absolute path whatever sub-path it was served from. */
export const PREFIX = "/__bench/projects";

/** Where a project's write lease is asked about, taken and let go (`lease.ts`) - beside the
 * projects rather than under them, because a lease is not a file in a project and is never on
 * a disk: it is the server's memory of who may write, and nothing more. The same host and
 * origin rules as the projects themselves. */
export const LEASES = "/__bench/leases";

/** The header a client names its lease holder id in - on every write, so the route can refuse
 * one from a client that does not hold the project, and on every lease it asks about. */
export const HOLDER = "x-bench-holder";

/** The header a client says what it is in, for somebody else to be told who holds a project
 * ("Chrome on a Mac"). Only ever shown, never trusted for anything. */
export const CLIENT = "x-bench-client";

/** The only kinds of file the route will write, rename or delete: a script, a values
 * document and a mesh. Compared without regard to case, because CAD tools write `.STL` at
 * least as often as `.stl` and it is the same kind of file either way. */
export const WRITABLE: readonly string[] = [".py", ".toml", ".stl"];

/** The largest body a write may carry. A mesh is the big one, and a printed part's STL is a
 * few megabytes; this is well past that and well short of filling a disk by accident. */
export const MAX_BODY = 64 * 1024 * 1024;

/** Why a request was not done. One word each, so a client can branch on it and a person
 * can read it. */
export type Reason =
  /** The `Host` header names a host this server was not told to answer to - DNS rebinding,
   * a hostile name pointed at a LAN address, which a same-origin check alone cannot see. */
  | "host"
  /** The request came from a page on another origin, or said it did. */
  | "origin"
  /** A project or file name that is not one plain name. */
  | "name"
  /** A file the route may not write: not `.py`, `.toml` or `.stl`. */
  | "type"
  /** The name resolves, through a symlink, to somewhere outside the root. */
  | "outside"
  /** A write, rename or delete aimed at a symbolic link: the route reads through a link
   * that stays inside the root, and never writes through one. */
  | "link"
  /** The host has no projects root where it was told to look. */
  | "no-root"
  /** Nothing there by that name. */
  | "missing"
  /** A create, or a rename onto a name, that is already taken. */
  | "exists"
  /** The file changed on disk since the version the write was made from. */
  | "moved"
  /** A write or delete that did not say which version it was made from. */
  | "precondition"
  /** A write to a project another client holds the write lease on (`lease.ts`). The message
   * says who. */
  | "leased"
  /** A method this path does not take. */
  | "method"
  /** A body over `MAX_BODY`. */
  | "too-large"
  /** The host tried and could not - a permission, a full disk. The message says which. */
  | "failed";

/** A request the route will not do, and why - the body of every answer that is not a 2xx. */
export interface Refusal {
  readonly refused: Reason;
  /** The HTTP status it is answered with. */
  readonly status: number;
  /** A sentence a person can read. */
  readonly message: string;
  /** `project/file` when the refusal is about one file - which file moved, which name was
   * taken - and `null` when it is not. */
  readonly file: string | null;
}

/** A refusal, with its status looked up from its reason. */
export const refusal = (refused: Reason, message: string, file: string | null = null): Refusal => ({
  refused,
  status: STATUS[refused],
  message,
  file,
});

const STATUS: Readonly<Record<Reason, number>> = {
  host: 403,
  origin: 403,
  name: 400,
  type: 403,
  outside: 403,
  link: 403,
  "no-root": 503,
  missing: 404,
  exists: 409,
  moved: 409,
  precondition: 428,
  // Locked: WebDAV's word for exactly this - the thing is held, and by somebody else.
  leased: 423,
  method: 405,
  "too-large": 413,
  failed: 500,
};

/** What a request is for, once it has been allowed. */
export type Operation =
  /** `GET /__bench/projects` - the projects under the root. */
  | { readonly op: "projects" }
  /** `GET /__bench/projects/<project>` - the files in one. */
  | { readonly op: "files"; readonly project: string }
  /** `GET /__bench/projects/<project>/<file>` - one file's bytes and version. */
  | { readonly op: "read"; readonly project: string; readonly file: string }
  /** `PUT` with `If-Match: "<version>"` - replace a file that is still at `base`. */
  | (Changing & { readonly op: "write"; readonly file: string; readonly base: string })
  /** `PUT` with `If-None-Match: *` - a new file, and the project directory if it is new too. */
  | (Changing & { readonly op: "create"; readonly file: string })
  /** `POST …?to=<name>` - the file under another name in the same project. */
  | (Changing & { readonly op: "rename"; readonly file: string; readonly to: string })
  /** `DELETE` with `If-Match: "<version>"` - the file, if it is still at `base`. */
  | (Changing & { readonly op: "delete"; readonly file: string; readonly base: string })
  /** `GET /__bench/leases/<project>` to be told, `POST …?act=take|take-over|release` to act on
   * the project's write lease (`lease.ts`). `holder` is `null` only for a look from a client
   * that holds nothing. */
  | {
      readonly op: "lease";
      readonly project: string;
      readonly act: Act;
      readonly holder: string | null;
      readonly label: string | undefined;
    };

/** What every operation that changes a project carries beside its own fields: the project, and
 * the lease holder id the client sent - `null` from a client that sent none, which may change a
 * project nobody holds and no other (`lease.ts`'s `heldAgainst`). */
export interface Changing {
  readonly project: string;
  readonly holder: string | null;
}

/** The parts of a request the decision is made from. Header names lower case, as Node gives
 * them; a header that was not sent is `undefined`. */
export interface Asked {
  readonly method: string;
  readonly url: string;
  readonly scheme: "http" | "https";
  readonly host: string | undefined;
  readonly origin: string | undefined;
  readonly fetchSite: string | undefined;
  readonly ifMatch: string | undefined;
  readonly ifNoneMatch: string | undefined;
  /** `x-bench-holder`: the lease holder id the client asks as. */
  readonly holder: string | undefined;
  /** `x-bench-client`: what the client says it is. */
  readonly client: string | undefined;
}

/** What the server was told it may be called: Vite's own `allowedHosts`, `true` for any. */
export type AllowedHosts = true | readonly string[];

/** Why `name` is not one plain name, or `null` if it is. */
export function nameProblem(name: string): string | null {
  if (name === "") return "a name cannot be empty";
  if (name === "." || name === "..") return `"${name}" is not a name`;
  if (name.includes("/") || name.includes("\\")) return `"${name}" has a path separator in it`;
  // NUL truncates a path in C beneath Node; the rest have no business in a file name.
  if ([...name].some((c) => c.charCodeAt(0) < 0x20 || c === "\x7f")) {
    return `"${JSON.stringify(name).slice(1, -1)}" has a control character in it`;
  }
  // Hidden files are the maker's own (`.git`, `.env`) and where a write stages its bytes.
  if (name.startsWith(".")) return `"${name}" is hidden`;
  if (name.length > 255) return "a name that long is not one a disk will take";
  return null;
}

/** Whether the route may write a file called `name`. */
export const writable = (name: string): boolean => {
  const dot = name.lastIndexOf(".");
  return dot > 0 && WRITABLE.includes(name.slice(dot).toLowerCase());
};

/** Whether `candidate` is strictly inside `root`, both already resolved through every
 * symlink. Inside means under `root` followed by a separator - a bare prefix would take
 * `/projects-evil` for part of `/projects`. `root` itself is not inside itself. */
export function within(root: string, candidate: string, sep = "/"): boolean {
  const under = root.endsWith(sep) ? root : root + sep;
  return candidate.startsWith(under) && candidate.length > under.length;
}

/** The host part of a `Host` header: no port, no brackets. */
function hostname(host: string): string {
  const trimmed = host.trim().toLowerCase();
  if (trimmed.startsWith("[")) return trimmed.slice(1, trimmed.indexOf("]"));
  const colon = trimmed.indexOf(":");
  return colon === -1 ? trimmed : trimmed.slice(0, colon);
}

const IPV4 = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

/** Why the `Host` header is refused, or `null`. The same rule Vite's own host check keeps -
 * an IP literal, `localhost` and anything under `.localhost` always, a name only when it is
 * in `allowedHosts` (a leading `.` meaning "and everything under it") - because Vite's check
 * runs *after* any middleware a plugin adds and so never sees this route. An address is
 * always fine: a tablet reaching the host as `192.168.1.20` is the case decision-9 exists
 * for, and rebinding needs a *name* to rebind. */
export function hostRefused(host: string | undefined, allowed: AllowedHosts): Refusal | null {
  if (allowed === true) return null;
  if (host === undefined || host.trim() === "") {
    return refusal("host", "the request did not say which host it was for");
  }
  const name = hostname(host);
  if (host.trim().startsWith("[") && name.includes(":")) return null;
  if (IPV4.test(name) || name === "localhost" || name.endsWith(".localhost")) return null;
  const listed = allowed.some((one) =>
    one.startsWith(".") ? name === one.slice(1) || name.endsWith(one) : name === one,
  );
  if (listed) return null;
  return refusal(
    "host",
    `this server does not answer to "${name}" - add it to allowedHosts in vite.config.ts if it should`,
  );
}

/** Why the request's origin is refused, or `null`.
 *
 * Same origin is the server's own scheme and the `Host` the request was sent to - not a list
 * of names that count as local, because a tablet on the LAN reaches the host by an address
 * nobody wrote down. `Sec-Fetch-Site` is taken at its word when a browser sends it, and only
 * `same-origin` or `none` (typed into the address bar) passes: `same-site` is another port on
 * the same machine, which is exactly another tab's dev server. `Origin: null` - a sandboxed
 * frame, a `file://` page - is another origin.
 *
 * **No `Origin` at all is let through.** Every browser sends one on a `PUT`, `POST` or
 * `DELETE`, same-origin or not, so its absence means a client that is not a browser page -
 * `curl`, a script, `tools.qa` - and the attack this stops is a page in another tab borrowing
 * the maker's browser. Something that can send its own requests can send its own `Origin`
 * too; keeping *that* out is not something a header check can do, and this does not pretend
 * to.
 */
export function originRefused(asked: Asked): Refusal | null {
  const site = asked.fetchSite?.toLowerCase();
  if (site !== undefined && site !== "same-origin" && site !== "none") {
    return refusal("origin", `a ${site} page may not use this route`);
  }
  if (asked.origin === undefined) return null;
  const own = asked.host === undefined ? null : `${asked.scheme}://${asked.host.trim().toLowerCase()}`;
  if (own !== null && asked.origin.trim().toLowerCase() === own) return null;
  return refusal("origin", `a page from ${asked.origin} may not use this route`);
}

/** The version an `If-Match` names: the tag without its quotes, or `null` for none. A weak
 * tag (`W/"…"`) is not a version this route hands out, so it names nothing. */
function tag(header: string | undefined): string | null {
  const trimmed = header?.trim();
  if (trimmed === undefined || !trimmed.startsWith('"') || !trimmed.endsWith('"') || trimmed.length < 3) {
    return null;
  }
  return trimmed.slice(1, -1);
}

/** A segment of the path, decoded once and checked as a name. */
function segment(raw: string): string | Refusal {
  let name: string;
  try {
    name = decodeURIComponent(raw);
  } catch {
    return refusal("name", `"${raw}" is not a name`);
  }
  const problem = nameProblem(name);
  return problem === null ? name : refusal("name", problem);
}

const isRefusal = (found: unknown): found is Refusal =>
  typeof found === "object" && found !== null && "refused" in found;

/** What `asked` is for, a refusal saying why it will not be done, or `null` when the URL is
 * not this route's at all and the next middleware should have it. */
export function decided(asked: Asked, allowed: AllowedHosts): Operation | Refusal | null {
  const cut = asked.url.search(/[?#]/);
  const path = cut === -1 ? asked.url : asked.url.slice(0, cut);
  const query = cut === -1 ? "" : asked.url.slice(cut + 1).split("#")[0] ?? "";
  const leasing = path === LEASES || path.startsWith(`${LEASES}/`);
  if (!leasing && path !== PREFIX && !path.startsWith(`${PREFIX}/`)) return null;

  const refused = hostRefused(asked.host, allowed) ?? originRefused(asked);
  if (refused !== null) return refused;

  // Sent or not, a holder id that is not one is refused rather than read as none: a client
  // that thinks it holds a lease and is quietly treated as holding nothing would be told its
  // writes went nowhere for a reason it cannot see.
  const holder = asked.holder?.trim() ?? null;
  if (holder !== null) {
    const problem = holderProblem(holder);
    if (problem !== null) return refusal("precondition", problem);
  }
  if (leasing) return leaseDecided(asked, path, query, holder);

  const rest = path.slice(PREFIX.length + 1);
  const raw = rest === "" ? [] : rest.split("/");
  if (raw.length > 2) {
    return refusal("name", "a path under the route is a project and a file, and nothing deeper");
  }
  const names: string[] = [];
  for (const one of raw) {
    const found = segment(one);
    if (isRefusal(found)) return found;
    names.push(found);
  }
  const [project, file] = names;
  const method = asked.method.toUpperCase();

  if (project === undefined) {
    return method === "GET" ? { op: "projects" } : refusal("method", `${method} the projects root`);
  }
  if (file === undefined) {
    return method === "GET" ? { op: "files", project } : refusal("method", `${method} a project`);
  }
  const at = `${project}/${file}`;
  if (method === "GET") return { op: "read", project, file };
  if (method !== "PUT" && method !== "POST" && method !== "DELETE") {
    return refusal("method", `${method} a file`, at);
  }
  if (!writable(file)) {
    return refusal("type", `only ${WRITABLE.join(", ")} files can be changed here`, at);
  }
  if (method === "POST") {
    const to = new URLSearchParams(query).get("to");
    if (to === null) return refusal("name", "a rename says what to call the file, as ?to=", at);
    const problem = nameProblem(to);
    if (problem !== null) return refusal("name", problem, at);
    if (!writable(to)) {
      return refusal("type", `only ${WRITABLE.join(", ")} files can be changed here`, `${project}/${to}`);
    }
    return { op: "rename", project, holder, file, to };
  }
  const base = tag(asked.ifMatch);
  if (method === "DELETE") {
    return base === null
      ? refusal("precondition", "a delete says which version it saw, as If-Match", at)
      : { op: "delete", project, holder, file, base };
  }
  if (base !== null) return { op: "write", project, holder, file, base };
  if (asked.ifNoneMatch?.trim() === "*") return { op: "create", project, holder, file };
  return refusal(
    "precondition",
    "a write says which version it was made from (If-Match) or that the file is new (If-None-Match: *)",
    at,
  );
}

/** A request under `LEASES`: one project, looked at with `GET`, or acted on with `POST` and
 * `?act=` - which needs a holder to act as. A project that has no directory yet can be leased:
 * a fresh host's first example, or a project just made, is open before its first file lands. */
function leaseDecided(asked: Asked, path: string, query: string, holder: string | null): Operation | Refusal {
  const rest = path.slice(LEASES.length + 1);
  const raw = rest === "" ? [] : rest.split("/");
  const [one] = raw;
  if (one === undefined || raw.length > 1) return refusal("name", "a lease is asked for by one project's name");
  const project = segment(one);
  if (isRefusal(project)) return project;
  const method = asked.method.toUpperCase();
  const label = asked.client;
  if (method === "GET") return { op: "lease", project, act: "look", holder, label };
  if (method !== "POST") return refusal("method", `${method} a lease`);
  const act = new URLSearchParams(query).get("act");
  if (act === null || act === "look" || !ACTS.includes(act as Act)) {
    return refusal("name", "a lease is acted on as ?act=take, ?act=take-over or ?act=release");
  }
  if (holder === null) return refusal("precondition", `a lease is taken or let go by a holder, named as ${HOLDER}`);
  return { op: "lease", project, act: act as Act, holder, label };
}
