/** The projects on the host, as functions: the client for the route `src/route.ts` decides
 * and `server/projects.ts` serves.
 *
 * Plain `fetch` over data, the way `bridge.ts` is plain `postMessage` over data, so nothing
 * above this knows it is talking to a server. Not used by the app yet - task-52 puts the
 * project store over it - which is why it is a thin, typed mapping of the route and nothing
 * more: no retries, no outbox, no opinion about what a refusal should do on screen.
 *
 * **A refusal is an answer, not an exception.** Every call resolves to `{ ok: true, … }` or
 * `{ ok: false, refusal }`, and a refusal carries the route's own reason - `moved`, `exists`,
 * `origin` - so a caller branches on a word rather than on a status code. What *does* reject
 * is not being able to ask at all: the network is down, the page has no host behind it. The
 * two are different, and `store.ts` is explicit that a caller must be able to tell them apart.
 */
import { PREFIX, type Refusal, refusal } from "./route";

/** Which bytes a file held when it was read or written: what a later write or delete names
 * as its base, and the modification time a person is shown. */
export interface Version {
  /** A hash of the bytes. Sent back as `If-Match`; a file whose hash has moved is not
   * overwritten. */
  readonly version: string;
  readonly mtimeMs: number;
  readonly size: number;
}

/** One file in a project, as a listing shows it. */
export interface Entry {
  readonly name: string;
  readonly mtimeMs: number;
  readonly size: number;
}

/** What the route answered: the thing asked for, or why not. */
export type Answer<T> = { readonly ok: true; readonly value: T } | { readonly ok: false; readonly refusal: Refusal };

/** The projects under the root, and where the root is - so anything that is about to write
 * there can name the directory first, as decision-9 asks. */
export interface Projects {
  readonly root: string;
  readonly projects: readonly string[];
}

/** A file's bytes, and which version they are. */
export interface Read {
  readonly bytes: Uint8Array;
  readonly version: Version;
}

/** The route, as calls. */
export interface Host {
  projects(): Promise<Answer<Projects>>;
  files(project: string): Promise<Answer<readonly Entry[]>>;
  read(project: string, file: string): Promise<Answer<Read>>;
  /** Replace `file`, which must still be at `base`; the version it is now. */
  write(project: string, file: string, bytes: Uint8Array | string, base: string): Promise<Answer<Version>>;
  /** A new file - and a new project, if `project` is not one yet. Refused if it is there. */
  create(project: string, file: string, bytes: Uint8Array | string): Promise<Answer<Version>>;
  /** `file` under the name `to`, in the same project. Refused if `to` is taken. */
  rename(project: string, file: string, to: string): Promise<Answer<Version>>;
  /** Delete `file`, which must still be at `base`. For now this is gone from the disk;
   * task-48 makes it recoverable. */
  remove(project: string, file: string, base: string): Promise<Answer<null>>;
}

const isRefusal = (body: unknown): body is Refusal =>
  typeof body === "object" && body !== null && "refused" in body && "message" in body;

/** Why a response that is not a 2xx was refused - the route's own reason when it gave one,
 * and a plain "failed" when something else answered (a static server with no route). */
async function refused(response: Response): Promise<Refusal> {
  try {
    const body: unknown = await response.json();
    if (isRefusal(body)) return body;
  } catch {
    // Not JSON: not the route talking.
  }
  return refusal("failed", `the host answered ${response.status} ${response.statusText}`.trim());
}

const versionFrom = (response: Response): Version => ({
  version: (response.headers.get("etag") ?? "").replace(/^"|"$/g, ""),
  mtimeMs: Number(response.headers.get("x-bench-mtime")),
  size: Number(response.headers.get("x-bench-size")),
});

const path = (...names: string[]): string =>
  [PREFIX, ...names.map((name) => encodeURIComponent(name))].join("/");

/** The route on the host at `origin` - the page's own when it is `""`, which is the only
 * one the route will take a write from; any other is for a caller outside a browser. */
export function host(origin = "", fetchImpl: typeof fetch = fetch): Host {
  const asked = async <T>(
    at: string,
    init: RequestInit,
    taken: (response: Response) => Promise<T>,
  ): Promise<Answer<T>> => {
    const response = await fetchImpl(`${origin}${at}`, { cache: "no-store", ...init });
    if (!response.ok) return { ok: false, refusal: await refused(response) };
    return { ok: true, value: await taken(response) };
  };
  const put = (headers: Record<string, string>, bytes: Uint8Array | string): RequestInit => ({
    method: "PUT",
    headers: { "content-type": "application/octet-stream", ...headers },
    body: typeof bytes === "string" ? bytes : new Blob([bytes as Uint8Array<ArrayBuffer>]),
  });
  return {
    projects: () => asked(PREFIX, {}, (r) => r.json() as Promise<Projects>),
    files: (project) =>
      asked(path(project), {}, async (r) => ((await r.json()) as { files: readonly Entry[] }).files),
    read: (project, file) =>
      asked(path(project, file), {}, async (r) => ({
        bytes: new Uint8Array(await r.arrayBuffer()),
        version: versionFrom(r),
      })),
    write: (project, file, bytes, base) =>
      asked(path(project, file), put({ "if-match": `"${base}"` }, bytes), (r) => r.json() as Promise<Version>),
    create: (project, file, bytes) =>
      asked(path(project, file), put({ "if-none-match": "*" }, bytes), (r) => r.json() as Promise<Version>),
    rename: (project, file, to) =>
      asked(`${path(project, file)}?to=${encodeURIComponent(to)}`, { method: "POST" }, (r) =>
        r.json() as Promise<Version>,
      ),
    remove: (project, file, base) =>
      asked(path(project, file), { method: "DELETE", headers: { "if-match": `"${base}"` } }, () =>
        Promise.resolve(null),
      ),
  };
}
