/** How the workspace `files.ts` knows maps onto the host: one directory per project under the
 * projects root, its scripts beside one `bench.toml` (decision-9).
 *
 * ```
 * $BENCH_PROJECTS/
 *   gridfinity_cabinet/
 *     bench.toml            [project] entry, [values], [reference]
 *     gridfinity_cabinet.py
 *     drawer-slide.stl      a dropped body (`main.ts` sends it straight through)
 * ```
 *
 * **Nothing here says which project is open.** That is each browser's own (`files.ts`), so a
 * desktop switching projects never moves a tablet looking at the same host. task-52's interim
 * mapping kept it in a `_workspace.toml` on the host, and that file is gone with the rest of
 * that mapping: every project in one `workspace/` directory as `<name>.py` beside
 * `<name>.toml`. Nothing shipped wrote that shape for real - the host store only ever switched
 * on for a root already holding `workspace/` - so nothing reads it back either; a
 * `workspace/` left on a disk opens as one more project, of several scripts.
 *
 * **A directory from before `bench.toml` still opens.** One with a `<script>.toml` beside its
 * script - decision-3's shape, and what `tools/build.py` still reads until task-50 - is read
 * from that file; the next change to its values is written to `bench.toml`, and the old file
 * is left exactly where it was, because it is somebody's file and not this app's to delete.
 * Once `bench.toml` is there it wins.
 *
 * Pure: no `fetch`, no IndexedDB, nothing asynchronous. `store-host.ts` is the only caller,
 * and it is what turns these into real reads and writes.
 */
import { type Project, type Workspace, declaredEntry, document, entryFor, readDocument } from "./files";
import { BENCH, tomlName } from "./values";

/** One file this mapping needs written, and the text it needs written as. */
export interface FileWrite {
  readonly project: string;
  readonly file: string;
  readonly text: string;
}

/** One file this mapping needs gone. */
export interface FileRemoval {
  readonly project: string;
  readonly file: string;
}

/** What a projects root holds, as far as this mapping reads it: each project directory's name,
 * and in it each file's name and text. */
export type Directories = ReadonlyMap<string, ReadonlyMap<string, string>>;

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

/** Whether `a` and `b` would write the same `bench.toml` - compared as what they mean rather
 * than as text, so a document read back and kept again is not rewritten over a hand-written
 * comment in it. */
const sameDocument = (a: Project, b: Project): boolean =>
  a.entry === b.entry &&
  sameValue(a.overrides, b.overrides) &&
  sameValue(a.reference, b.reference) &&
  sameValue({ ...a.kept, entry: null }, { ...b.kept, entry: null });

/** Every file `next` needs on the host to be read back exactly as it is: each project's
 * scripts and its `bench.toml`. */
export function filesFor(next: Workspace): readonly FileWrite[] {
  return writesFor(null, next);
}

/** Only the files that changed between `previous` (what was last kept - `null` for nothing
 * yet) and `next`, compared project by project and file by file - a script and the document
 * compared *separately*, so typing in a script never rewrites `bench.toml` and a panel edit
 * never rewrites a script. A workspace read back from the host and kept again unchanged writes
 * nothing, which is what keeps a boot from rewriting anything underneath a maker's own editor
 * - and which project is open is not compared at all, since no file says it. */
export function writesFor(previous: Workspace | null, next: Workspace): readonly FileWrite[] {
  const writes: FileWrite[] = [];
  const before = new Map((previous?.projects ?? []).map((one) => [one.name, one]));
  for (const one of next.projects) {
    const was = before.get(one.name);
    for (const [file, text] of Object.entries(one.scripts)) {
      if (was?.scripts[file] !== text) writes.push({ project: one.name, file, text });
    }
    // A document this version could not read is never regenerated over (`Kept.unreadable`);
    // a new project carrying one - adopted from a browser - gets it written as it was.
    const regenerated = was !== undefined && !sameDocument(was, one) && one.kept.unreadable === undefined;
    if (was === undefined || regenerated) {
      writes.push({ project: one.name, file: BENCH, text: document(one) });
    }
  }
  return writes;
}

/** The files `previous` had and `next` no longer does: every file of a project renamed away
 * from or deleted, and a script gone from a project that is still there.
 *
 * A project renamed or deleted as a whole is not this: the store moves its directory in one
 * step (`ProjectStore.renameProject`, `trashProject`) and forgets it here, so what is left for
 * this is a script gone from a project that is still there - each removal a move into the
 * trash under the root, never an unlink. */
export function removalsFor(previous: Workspace | null, next: Workspace): readonly FileRemoval[] {
  if (previous === null) return [];
  const now = new Map(next.projects.map((one) => [one.name, one]));
  const gone: FileRemoval[] = [];
  for (const one of previous.projects) {
    const kept = now.get(one.name);
    for (const file of Object.keys(one.scripts)) {
      if (kept?.scripts[file] === undefined) gone.push({ project: one.name, file });
    }
    if (kept === undefined) gone.push({ project: one.name, file: BENCH });
  }
  return gone;
}

/** Whether `file` is one this mapping reads: a script, or a TOML document - `bench.toml`, or
 * a `<script>.toml` from before it. An STL is read by nobody here: it is bytes, not text, and
 * `main.ts` asks for the one a project's `[reference]` names when it needs it. */
export const owned = (file: string): boolean => file.endsWith(".py") || file.endsWith(".toml");

/** The script a project directory runs: the `entry` its document declares when that is one of
 * its scripts, else the one named for the directory, else the first by name. */
function entryOf(name: string, scripts: readonly string[], declared: string | null): string | null {
  if (declared !== null && scripts.includes(declared)) return declared;
  if (scripts.includes(entryFor(name))) return entryFor(name);
  return scripts[0] ?? null;
}

/** One project directory, read: `null` when it holds no script, which is not a project this
 * version can open - an empty directory a rename or a delete left behind (`removalsFor`), or
 * one somebody made by hand and has not written anything in yet. */
function projectFrom(name: string, files: ReadonlyMap<string, string>): Project | null {
  const scripts = [...files.keys()].filter((file) => file.endsWith(".py")).sort();
  const bench = files.get(BENCH);
  const declared = declaredEntry(bench);
  const entry = entryOf(name, scripts, declared);
  if (entry === null) return null;
  const read = readDocument(bench ?? files.get(tomlName(entry)));
  const texts: Record<string, string> = {};
  for (const file of scripts) texts[file] = files.get(file) ?? "";
  return { name, entry, scripts: texts, ...read };
}

/** The workspace `directories` read back as - `null` when not one of them is a project, which
 * is a host with nothing kept yet. Opens on the first project by name, at its entry: which
 * project a person actually had open is the browser's to say, not the host's, and `main.ts`
 * puts it back from there. */
export function workspaceFrom(directories: Directories): Workspace | null {
  const projects: Project[] = [];
  for (const name of [...directories.keys()].sort()) {
    const files = directories.get(name);
    const found = files === undefined ? null : projectFrom(name, files);
    if (found !== null) projects.push(found);
  }
  const first = projects[0];
  if (first === undefined) return null;
  return { projects, current: first.name, script: first.entry };
}
