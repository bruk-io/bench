/** How the workspace `files.ts` already knows maps onto files under one project directory on
 * the host, until task-46 gives every project a directory of its own.
 *
 * decision-3 shipped `<script>.py` beside `<script>.toml` on the command line, and this keeps
 * exactly that pairing - all of them under one project directory (`PROJECT`) rather than one
 * directory per script, because splitting the workspace into per-project directories is
 * task-46's own move. Choosing the pairing task-46 already assumes means exploding `workspace/`
 * into one directory per script is a rename of what is already there, not a rewrite of how it
 * is written.
 *
 * Pure: no `fetch`, no IndexedDB, nothing asynchronous. `store-host.ts` is the only caller,
 * and it is what turns these into real reads and writes.
 */
import { type Project, type Workspace, document as projectToml } from "./files";
import { fromToml, tomlName } from "./values";

/** The one project directory the browser's workspace lives under, until task-46. */
export const PROJECT = "workspace";

/** The file naming which project is open - not a project's own values file, so it carries no
 * `[values]` or `[reference]` table and is never paired with a `.py`. Reserved: a script
 * actually called `_workspace.py` would collide with it, which `route.ts`'s `nameProblem`
 * does not forbid - unlikely enough that this is a documented limitation rather than a check. */
export const MANIFEST = "_workspace.toml";

/** One file this mapping needs written, and the text it needs written as. */
export interface FileWrite {
  readonly file: string;
  readonly text: string;
}

const manifest = (current: string): string => `current = ${JSON.stringify(current)}\n`;

const CURRENT = /^current\s*=\s*"((?:[^"\\]|\\.)*)"/m;

/** The project named `current = "…"` in a manifest's text, or `null` when it cannot be read. */
function currentIn(text: string): string | null {
  const found = CURRENT.exec(text);
  if (found === null) return null;
  try {
    return JSON.parse(`"${found[1] ?? ""}"`) as string;
  } catch {
    return null;
  }
}

/** Deep equality that does not care about key order - two `Overrides` or `ReferenceTable`
 * values built by different code paths (typed by hand here, parsed from TOML there) compare
 * equal when they mean the same thing. */
function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null || typeof a !== "object") return false;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((value, at) => sameValue(value, b[at]));
  }
  const left = a as Record<string, unknown>;
  const right = b as Record<string, unknown>;
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  return [...keys].every((key) => sameValue(left[key], right[key]));
}

const sameProject = (a: Project, b: Project): boolean =>
  a.source === b.source && sameValue(a.overrides, b.overrides) && sameValue(a.reference, b.reference);

/** Every file `next` needs on the host to be read back exactly as it is: one `.py` and one
 * `.toml` per project, and the manifest naming which is open. */
export function filesFor(next: Workspace): readonly FileWrite[] {
  const writes: FileWrite[] = [];
  for (const project of next.files) {
    writes.push({ file: project.name, text: project.source });
    writes.push({ file: tomlName(project.name), text: projectToml(project, []) });
  }
  writes.push({ file: MANIFEST, text: manifest(next.current) });
  return writes;
}

/** Only the files that changed between `previous` (what was last kept - `null` for nothing
 * yet) and `next`, compared project by project rather than as text: a workspace read back from
 * the host and kept again unchanged writes nothing, which is what keeps a boot from rewriting
 * a script's own hand-edited values file underneath it. */
export function writesFor(previous: Workspace | null, next: Workspace): readonly FileWrite[] {
  const writes: FileWrite[] = [];
  const before = new Map((previous?.files ?? []).map((project) => [project.name, project]));
  for (const project of next.files) {
    const was = before.get(project.name);
    if (was === undefined || !sameProject(was, project)) {
      writes.push({ file: project.name, text: project.source });
      writes.push({ file: tomlName(project.name), text: projectToml(project, []) });
    }
  }
  if (previous === null || previous.current !== next.current) {
    writes.push({ file: MANIFEST, text: manifest(next.current) });
  }
  return writes;
}

/** The files `previous` had and `next` no longer does - a project renamed away from or
 * deleted, whose script and values file both have to go. */
export function removalsFor(previous: Workspace | null, next: Workspace): readonly string[] {
  if (previous === null) return [];
  const kept = new Set(next.files.map((project) => project.name));
  const gone: string[] = [];
  for (const project of previous.files) {
    if (kept.has(project.name)) continue;
    gone.push(project.name, tomlName(project.name));
  }
  return gone;
}

/** Whether `file` is one this mapping ever writes: a script, a values file paired with one
 * (`.toml` files with no `.py` twin are somebody else's, and are read past rather than read
 * as a project's own), or the manifest. */
export function owned(file: string, scripts: ReadonlySet<string>): boolean {
  if (file === MANIFEST || file.endsWith(".py")) return true;
  if (!file.endsWith(".toml")) return false;
  return scripts.has(`${file.slice(0, -".toml".length)}.py`);
}

/** The workspace `entries` (a file name to its text, everything this mapping wrote and
 * nothing else) reads back as - `null` when there is not one script in it, which is a host
 * with nothing kept yet. A `.toml` that cannot be read (`values.ts`'s `fromToml`, exactly as
 * `files.ts`'s `fieldsOf` already treats one) opens as a project with no values file, on the
 * script's own defaults, rather than losing the script over it. */
export function workspaceFrom(entries: ReadonlyMap<string, string>): Workspace | null {
  const scripts = [...entries.keys()].filter((name) => name.endsWith(".py")).sort();
  if (scripts.length === 0) return null;
  const files: Project[] = scripts.map((name) => {
    const source = entries.get(name) ?? "";
    const tomlText = entries.get(tomlName(name));
    const read = tomlText === undefined ? undefined : fromToml(tomlText);
    return {
      name,
      source,
      overrides: read?.ok === true ? read.values : {},
      reference: read?.ok === true ? read.reference : null,
    };
  });
  const manifestText = entries.get(MANIFEST);
  const wanted = manifestText === undefined ? null : currentIn(manifestText);
  const first = files[0];
  if (first === undefined) return null;
  const current = wanted !== null && files.some((project) => project.name === wanted) ? wanted : first.name;
  return { files, current };
}
