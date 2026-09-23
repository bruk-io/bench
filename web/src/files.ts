/** The projects a person keeps: directories on the host, one of them open.
 *
 * A project is a directory (decision-9): its scripts, and one `bench.toml` holding the values,
 * the `[reference]` placement and a `[project]` table naming the `entry` - the script a fresh
 * open of the project runs. The script says what a thing is, the values say which one of it
 * you are building (decision-3), and a project's scripts and its document go everywhere
 * together - renamed, deleted, duplicated and handed over as one directory. In memory the
 * values are the panel's table (`overrides.ts`); kept, they are the TOML document
 * (`values.ts`), so what the host holds is a file a person can read in a diff and not a blob.
 *
 * **Which project is open, and which of its scripts, is this browser's business and nothing
 * else's.** `current` and `script` ride in the workspace because the page needs them, but a
 * store never keeps them: a desktop and a tablet on the same host each have their own, and one
 * switching must not move the other (task-47's case). `main.ts` remembers them in `storage.ts`.
 *
 * **The entry runs by default; the script a person has open is what runs.** decision-9's own
 * answer to "which script runs": opening a project opens its `entry`, and opening another of its
 * scripts makes that the one Run runs - `entry` does not change because a person looked at
 * another file.
 *
 * Plain data and functions over it, as `overrides.ts` is: no DOM and no storage. Every function
 * here keeps three things true of the workspace it returns: there is at least one project,
 * `current` names one of them, and `script` names one of its scripts.
 */
import { type Overrides, parsed } from "./overrides";
import { nameProblem as plainProblem } from "./route";
import { type Kept, NOTHING_KEPT, type ReferenceTable, fromToml, keptOf, stemOf, toml } from "./values";

export interface Project {
  /** The directory, under the host's projects root. */
  readonly name: string;
  /** The script a fresh open of this project runs - `[project] entry`. Always one of
   * `scripts`. */
  readonly entry: string;
  /** Every script in the directory, by file name. */
  readonly scripts: Readonly<Record<string, string>>;
  readonly overrides: Overrides;
  /** The `[reference]` table this project's document was opened with, or `null` for one with
   * none - decision-4's placement. Not a script's own values: it is about the body a maker
   * drops, not the thing being built, so it rides beside `overrides` rather than in it. */
  readonly reference: ReferenceTable | null;
  /** What the document held that this version does not read, put back on every write so a
   * newer file is not cut down to what this one understands (`values.ts`'s `Kept`). Its own
   * `entry` is always `null` here: `entry` above is the truth, and is what is written. */
  readonly kept: Kept;
}

export interface Workspace {
  readonly projects: readonly Project[];
  /** The open project - this browser's, never kept by a store. */
  readonly current: string;
  /** The open script in the open project - likewise. */
  readonly script: string;
}

/** What a new project is called before a person names it. */
export const UNTITLED = "untitled";

const SCRIPT = ".py";

/** The script a project called `name` is born with: named for it, as a one-script project
 * from before directories always was. */
export const entryFor = (name: string): string => `${name}${SCRIPT}`;

/** A project of one script, named for it. */
export const project = (
  name: string,
  source: string,
  overrides: Overrides = {},
  reference: ReferenceTable | null = null,
  kept: Kept = NOTHING_KEPT,
): Project => ({
  name,
  entry: entryFor(name),
  scripts: { [entryFor(name)]: source },
  overrides,
  reference,
  kept: { ...kept, entry: null },
});

/** A workspace of one project of one script, open. */
export const single = (
  name: string,
  source: string,
  overrides: Overrides = {},
  reference: ReferenceTable | null = null,
): Workspace => ({
  projects: [project(name, source, overrides, reference)],
  current: name,
  script: entryFor(name),
});

/** The open project. */
export function opened(space: Workspace): Project {
  const found = space.projects.find((one) => one.name === space.current);
  // Unreachable through this module, which never returns a workspace without it.
  if (found === undefined) throw new Error(`the workspace has no project called ${space.current}`);
  return found;
}

/** The text of the script that is open - the one a run runs. */
export const openSource = (space: Workspace): string => opened(space).scripts[space.script] ?? "";

/** The open project's other scripts, by name - everything :func:`openSource` is not. What a
 * run hands the worker (task-50, decision-9 step 9) so the open script can import them, and
 * what `tools/build.py` puts on the import path beside the entry it runs. Empty for a project
 * of one script, which is most of them - a run with nothing here mounts nothing. */
export function modulesOf(space: Workspace): Readonly<Record<string, string>> {
  const project = opened(space);
  const out: Record<string, string> = {};
  for (const [name, text] of Object.entries(project.scripts)) {
    if (name !== space.script) out[name] = text;
  }
  return out;
}

/** A project's scripts, its entry first and the rest by name - the order their tabs take. */
export const scriptsOf = (one: Project): readonly string[] => [
  one.entry,
  ...Object.keys(one.scripts)
    .filter((name) => name !== one.entry)
    .sort(),
];

const names = (space: Workspace): readonly string[] => space.projects.map((one) => one.name);

const changed = (space: Workspace, change: (one: Project) => Project): Workspace => ({
  ...space,
  projects: space.projects.map((one) => (one.name === space.current ? change(one) : one)),
});

/** The open script with its text replaced. */
export const withSource = (space: Workspace, source: string): Workspace =>
  changed(space, (one) => ({ ...one, scripts: { ...one.scripts, [space.script]: source } }));

/** The open project with its values replaced. */
export const withOverrides = (space: Workspace, overrides: Overrides): Workspace =>
  changed(space, (one) => ({ ...one, overrides }));

/** The open project with its `[reference]` table replaced - what *Open…* on a `.toml` does
 * for the project it lands on, the same way it already replaces the values. */
export const withReference = (space: Workspace, reference: ReferenceTable | null): Workspace =>
  changed(space, (one) => ({ ...one, reference }));

/** The open project with `kept` as what its document holds beyond what this version reads. */
export const withKept = (space: Workspace, kept: Kept): Workspace => changed(space, (one) => ({ ...one, kept: { ...kept, entry: null } }));

/** The open project with another of its scripts open - or unchanged, when it has none by that
 * name. `entry` stays what it was: opening a file is not declaring it the project's entry. */
export const withScript = (space: Workspace, script: string): Workspace =>
  script in opened(space).scripts ? { ...space, script } : space;

/** A name as a person typed it, as a project is called: trimmed, and without a `.py` a person
 * who is used to naming scripts might still put on the end. */
export function normalized(typed: string): string {
  const trimmed = typed.trim();
  return trimmed.endsWith(SCRIPT) ? trimmed.slice(0, -SCRIPT.length).trim() : trimmed;
}

/** `wanted`, or the first of `wanted-2`, `wanted-3`, … that no project is called yet. */
export function freeName(taken: readonly string[], wanted: string): string {
  if (!taken.includes(wanted)) return wanted;
  for (let count = 2; ; count += 1) {
    const candidate = `${wanted}-${count}`;
    if (!taken.includes(candidate)) return candidate;
  }
}

/** Why the project called `from` cannot be renamed to what was typed, or `null` when it can.
 * A project is a directory on the host, so its name is held to the route's own rule for a
 * name (`route.ts`) as well as not being taken. */
export function nameProblem(taken: readonly string[], from: string, typed: string): string | null {
  const name = normalized(typed);
  if (name === "") return "a project needs a name";
  if (/[/\\]/.test(name)) return "a project name cannot have a slash in it";
  if (name.startsWith(".")) return "a project name cannot start with a dot";
  const plain = plainProblem(name);
  if (plain !== null) return plain;
  if (name !== from && taken.includes(name)) return `there is already a project called ${name}`;
  return null;
}

/** The workspace with a new project in it, open at its one script. Its name is `wanted`, or a
 * free one like it; its values are `overrides`, which is nothing for a script written here and
 * the values file's table for a project opened from disk. */
export function created(
  space: Workspace,
  wanted: string,
  source: string,
  overrides: Overrides = {},
  reference: ReferenceTable | null = null,
  kept: Kept = NOTHING_KEPT,
): Workspace {
  const name = freeName(names(space), wanted);
  return {
    projects: [...space.projects, project(name, source, overrides, reference, kept)],
    current: name,
    script: entryFor(name),
  };
}

/** `one` called `name`. A project whose entry is named for it keeps it named for it - the
 * one-script project every project from before directories is, where the script and the
 * directory are the same word and a person renaming one means both. Any other script keeps its
 * name: a directory rename does not rename the files in it. */
function called(one: Project, name: string): Project {
  if (one.entry !== entryFor(one.name) || one.name === name) return { ...one, name };
  const entry = entryFor(name);
  const scripts: Record<string, string> = {};
  for (const [file, text] of Object.entries(one.scripts)) scripts[file === one.entry ? entry : file] = text;
  return { ...one, name, entry, scripts };
}

/** The workspace with a copy of `name` beside it, open at its entry: the same scripts and the
 * same values under the next free name - or unchanged, when there is no such project. */
export function duplicated(space: Workspace, name: string): Workspace {
  const at = space.projects.findIndex((one) => one.name === name);
  const original = space.projects[at];
  if (original === undefined) return space;
  const copy = called(original, freeName(names(space), name));
  return {
    projects: [...space.projects.slice(0, at + 1), copy, ...space.projects.slice(at + 1)],
    current: copy.name,
    script: copy.entry,
  };
}

/** The workspace with `name` open, at its entry - a fresh open of a project runs what it
 * declares - or unchanged, when there is no such project. */
export function switched(space: Workspace, name: string): Workspace {
  const found = space.projects.find((one) => one.name === name);
  return found === undefined ? space : { ...space, current: name, script: found.entry };
}

/** The workspace with `from` called what was typed - or unchanged, when that name will not do.
 * Its values go with it, since they are in its own directory. */
export function renamed(space: Workspace, from: string, typed: string): Workspace {
  if (nameProblem(names(space), from, typed) !== null) return space;
  const name = normalized(typed);
  const was = space.projects.find((one) => one.name === from);
  if (was === undefined) return space;
  const now = called(was, name);
  const open = space.current === from;
  return {
    projects: space.projects.map((one) => (one.name === from ? now : one)),
    current: open ? name : space.current,
    script: open && space.script === was.entry ? now.entry : space.script,
  };
}

/** The workspace without `name`. Deleting the open project opens its neighbour; deleting the
 * last one leaves a new untitled one, from `starter`, since there is always something open. */
export function deleted(space: Workspace, name: string, starter: string): Workspace {
  const at = space.projects.findIndex((one) => one.name === name);
  if (at === -1) return space;
  const projects = space.projects.filter((one) => one.name !== name);
  const neighbour = projects[Math.min(at, projects.length - 1)];
  if (neighbour === undefined) return single(UNTITLED, starter);
  if (space.current !== name) return { ...space, projects };
  return { projects, current: neighbour.name, script: neighbour.entry };
}

/** `incoming` - the projects a browser kept, being adopted onto the host - beside what `space`
 * already holds, each under its own name or the next free one like it, so nothing on the host
 * is written over by something that happened to share a name. The first of them is opened, at
 * its entry. `space` is `null` for a host with nothing on it, where only `incoming` is kept -
 * or `incoming` is empty, in which case this is `space` unchanged, or `null`. */
export function merged(space: Workspace | null, incoming: readonly Project[]): Workspace | null {
  const projects = [...(space?.projects ?? [])];
  let first: Project | null = null;
  for (const one of incoming) {
    const moved = called(
      one,
      freeName(
        projects.map((other) => other.name),
        one.name,
      ),
    );
    projects.push(moved);
    first ??= moved;
  }
  if (first === null) return space;
  return { projects, current: first.name, script: first.entry };
}

/** Whether `one` is the example `file` exactly as it shipped: one script, that text, nothing
 * turned and nothing placed. */
const asShipped = (one: Project, file: string, source: string): boolean =>
  one.entry === file &&
  Object.keys(one.scripts).length === 1 &&
  one.scripts[file] === source &&
  Object.keys(one.overrides).length === 0 &&
  one.reference === null;

/** Whether `one` is nothing but one of `examples`, untouched - a project a browser kept only
 * because the app always used to open one, and not work anybody would want carried anywhere. */
export const pristine = (one: Project, examples: Readonly<Record<string, string>>): boolean =>
  Object.entries(examples).some(([file, source]) => asShipped(one, file, source));

/** The workspace with an example open. A project already holding that example, untouched, is
 * opened again rather than copied; otherwise the example arrives as a new project named for
 * it, so opening one never costs a person the script they were writing. */
export function withExample(space: Workspace, file: string, source: string): Workspace {
  const same = space.projects.find((one) => asShipped(one, file, source));
  return same === undefined ? created(space, stemOf(file), source) : switched(space, same.name);
}

/** The workspace as a store moves it: each project's scripts, and its document as the TOML it
 * is. `current` and `script` go too, because the browser's own store - which only adoption
 * reads now - kept them this way; a host store drops them (see the module comment). */
export const serialized = (space: Workspace): string =>
  JSON.stringify({
    projects: space.projects.map((one) => ({
      name: one.name,
      entry: one.entry,
      scripts: one.scripts,
      values: document(one),
    })),
    current: space.current,
    script: space.script,
  });

/** A project's document - its `bench.toml` - as it is kept, shown on its own tab and handed
 * over on download: `[project]` naming the entry, `[values]`, `[reference]` when it has one,
 * and whatever it was opened with that this version does not read, `order` given when a run
 * has said the script's own declaration order. */
export const document = (one: Project, order: readonly string[] = []): string =>
  one.kept.unreadable?.text ?? toml(one.overrides, one.entry, order, one.reference, { ...one.kept, entry: one.entry });

/** A project's document read back: its values, its placement, and what is kept beside them.
 * One that cannot be read opens on the script's own defaults and no placement, since the script
 * is worth more than the table - `tools/build.py` refuses such a file, and the explorer says so
 * when one is picked (`main.ts`) - and is kept whole (`Kept.unreadable`): shown as it is, and
 * never written over by a panel edit, which would cut it down to what the panel knows. */
export function readDocument(text: string | undefined): {
  overrides: Overrides;
  reference: ReferenceTable | null;
  kept: Kept;
} {
  if (text === undefined) return { overrides: {}, reference: null, kept: NOTHING_KEPT };
  const found = fromToml(text);
  if (!found.ok) {
    return { overrides: {}, reference: null, kept: { ...NOTHING_KEPT, unreadable: { text, problem: found.problem } } };
  }
  // `entry` is the project's own field, so the one in the document is not kept twice.
  return { overrides: found.values, reference: found.reference, kept: { ...keptOf(text), entry: null } };
}

/** The script a project's document names as its entry, or `null` when it names none. */
export const declaredEntry = (text: string | undefined): string | null =>
  text === undefined ? null : keptOf(text).entry;

/** Whether `name` is a script's file name the route would take: one plain `.py` name. */
const isScript = (name: string): boolean =>
  name.endsWith(SCRIPT) && name.length > SCRIPT.length && nameProblem([], "", stemOf(name)) === null;

/** One project read from a kept record in the shape `serialized` writes, or `null` when it is
 * not one. */
function projectOf(record: Record<string, unknown>): Project | null {
  const { name, entry, scripts, values } = record;
  if (typeof name !== "string" || nameProblem([], "", name) !== null || name !== normalized(name)) return null;
  if (typeof scripts !== "object" || scripts === null) return null;
  const kept: Record<string, string> = {};
  for (const [file, text] of Object.entries(scripts as Record<string, unknown>)) {
    if (isScript(file) && typeof text === "string") kept[file] = text;
  }
  const files = Object.keys(kept).sort();
  const first = files[0];
  if (first === undefined) return null;
  const named = typeof entry === "string" ? entry : declaredEntry(typeof values === "string" ? values : undefined);
  const declared = named !== null && named in kept ? named : null;
  return {
    name,
    entry: declared ?? (entryFor(name) in kept ? entryFor(name) : first),
    scripts: kept,
    ...readDocument(typeof values === "string" ? values : undefined),
  };
}

/** One project read from a record a browser kept before a project was a directory -
 * `{name: "cabinet.py", source, values}` - as the one-script directory decision-9 says it
 * becomes: named for the script's stem, the script its entry. A record from before the values
 * were a document holds an `overrides` object instead, read the way `overrides.ts` read one, so
 * a browser that kept its work under either old shape loses none of it. */
function legacyProjectOf(record: Record<string, unknown>): Project | null {
  const { name, source, values, overrides } = record;
  if (typeof name !== "string" || typeof source !== "string" || !isScript(name)) return null;
  const stem = stemOf(name);
  if (typeof values === "string") {
    const read = readDocument(values);
    return { name: stem, entry: name, scripts: { [name]: source }, ...read };
  }
  return {
    name: stem,
    entry: name,
    scripts: { [name]: source },
    overrides: overrides === undefined ? {} : parsed(JSON.stringify(overrides)),
    reference: null,
    kept: NOTHING_KEPT,
  };
}

/** A workspace read back from a store, or `null` when there is none worth keeping.
 *
 * Two shapes are read. The one `serialized` writes, and the one a browser kept before a
 * project was a directory (`files`, one script each - see `legacyProjectOf`), which is what
 * the one-time adoption of a browser's projects onto the host reads (task-46 AC#4). Projects
 * are checked one by one: one that is not a name and a script is dropped, a second of the same
 * name is dropped. An open project that did not survive gives way to the first that did, at
 * its entry.
 */
export function restored(said: string | null): Workspace | null {
  if (said === null) return null;
  let value: unknown;
  try {
    value = JSON.parse(said);
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null) return null;
  const { projects, files, current, script } = value as {
    projects?: unknown;
    files?: unknown;
    current?: unknown;
    script?: unknown;
  };
  const records = Array.isArray(projects) ? projects : Array.isArray(files) ? files : null;
  if (records === null) return null;
  const read = Array.isArray(projects) ? projectOf : legacyProjectOf;
  const kept: Project[] = [];
  for (const one of records as unknown[]) {
    if (typeof one !== "object" || one === null) continue;
    const found = read(one as Record<string, unknown>);
    if (found === null || kept.some((other) => other.name === found.name)) continue;
    kept.push(found);
  }
  const first = kept[0];
  if (first === undefined) return null;
  // The legacy shape named its open project by its script's file name.
  const wanted = typeof current === "string" ? (Array.isArray(projects) ? current : stemOf(current)) : null;
  const open = kept.find((one) => one.name === wanted) ?? first;
  const same = open.name === wanted && typeof script === "string" && script in open.scripts;
  return { projects: kept, current: open.name, script: same ? script : open.entry };
}

/** The workspace for a browser that kept one script, from before there were files: that
 * script as a project of its own, named for the example it still is when it is one. A browser
 * that kept nothing starts on `first` of the examples. */
export function adopted(
  source: string | null,
  overrides: Overrides,
  examples: Readonly<Record<string, string>>,
  first: string,
): Workspace {
  if (source === null) return single(stemOf(first), examples[first] ?? "", overrides);
  const example = Object.entries(examples).find(([, text]) => text === source)?.[0];
  return single(example === undefined ? UNTITLED : stemOf(example), source, overrides);
}
