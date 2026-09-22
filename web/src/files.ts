/** The projects a person keeps: named in the browser, one of them open.
 *
 * A project is a script and its values (decision-3): the script says what a thing is, the
 * values say which one of it you are building, and the two go everywhere together - renamed,
 * deleted, duplicated and handed over as a pair. In memory the values are the panel's table
 * (`overrides.ts`); kept, they are the TOML file `tools/build.py` reads from beside a script
 * on disk (`values.ts`), so what the browser remembers is a document and not a blob.
 *
 * Plain data and functions over it, as `overrides.ts` is: no DOM and no storage. The page owns
 * the one workspace there is, hands its names to the explorer, and writes the whole of it back
 * through `storage.ts` after every change. Each project keeps its own values, because a value
 * set on the Parameters tab belongs to the script that declared it, not to whichever script
 * happens to be open next.
 *
 * Every function here keeps two things true of the workspace it returns: there is at least
 * one project, and `current` names one of them.
 */
import { type Overrides, parsed } from "./overrides";
import { type ReferenceTable, fromToml, toml } from "./values";

export interface Project {
  readonly name: string;
  readonly source: string;
  readonly overrides: Overrides;
  /** The `[reference]` table this project's TOML was opened with, or `null` for one with
   * none - decision-4's placement, carried through every regeneration of the values file
   * even though the app cannot compose one yet. Not a script's own values: it is about the
   * body a maker drops, not the thing being built, so it rides beside `overrides` rather
   * than in it. */
  readonly reference: ReferenceTable | null;
}

export interface Workspace {
  readonly files: readonly Project[];
  readonly current: string;
}

/** What a new project is called before a person names it. */
export const UNTITLED = "untitled.py";

const EXTENSION = ".py";

/** A workspace of one project, open. */
export const single = (
  name: string,
  source: string,
  overrides: Overrides = {},
  reference: ReferenceTable | null = null,
): Workspace => ({
  files: [{ name, source, overrides, reference }],
  current: name,
});

/** The open project. */
export function opened(space: Workspace): Project {
  const found = space.files.find((file) => file.name === space.current);
  // Unreachable through this module, which never returns a workspace without it.
  if (found === undefined) throw new Error(`the workspace has no file called ${space.current}`);
  return found;
}

const names = (space: Workspace): readonly string[] => space.files.map((file) => file.name);

const changed = (space: Workspace, change: (file: Project) => Project): Workspace => ({
  ...space,
  files: space.files.map((file) => (file.name === space.current ? change(file) : file)),
});

/** The open project with its script replaced. */
export const withSource = (space: Workspace, source: string): Workspace =>
  changed(space, (file) => ({ ...file, source }));

/** The open project with its values replaced. */
export const withOverrides = (space: Workspace, overrides: Overrides): Workspace =>
  changed(space, (file) => ({ ...file, overrides }));

/** The open project with its `[reference]` table replaced - what *Open…* on a `.toml` does
 * for the project it lands on, the same way it already replaces the values. */
export const withReference = (space: Workspace, reference: ReferenceTable | null): Workspace =>
  changed(space, (file) => ({ ...file, reference }));

/** A name as a person typed it, as a project is called: trimmed, and ending in `.py`. */
export function normalized(typed: string): string {
  const trimmed = typed.trim();
  if (trimmed === "") return "";
  return trimmed.endsWith(EXTENSION) ? trimmed : `${trimmed}${EXTENSION}`;
}

/** `wanted`, or the first of `stem-2.py`, `stem-3.py`, … that no project is called yet. */
export function freeName(taken: readonly string[], wanted: string): string {
  if (!taken.includes(wanted)) return wanted;
  const stem = wanted.endsWith(EXTENSION) ? wanted.slice(0, -EXTENSION.length) : wanted;
  for (let count = 2; ; count += 1) {
    const candidate = `${stem}-${count}${EXTENSION}`;
    if (!taken.includes(candidate)) return candidate;
  }
}

/** Why the project called `from` cannot be renamed to what was typed, or `null` when it can. */
export function nameProblem(taken: readonly string[], from: string, typed: string): string | null {
  const name = normalized(typed);
  if (name === "" || name === EXTENSION) return "a file needs a name";
  if (/[/\\]/.test(name)) return "a file name cannot have a slash in it";
  if (name !== from && taken.includes(name)) return `there is already a file called ${name}`;
  return null;
}

/** The workspace with a new project in it, open. Its name is `wanted`, or a free one like
 * it; its values are `overrides`, which is nothing for a script written here and the values
 * file's table for a project opened from disk. */
export function created(
  space: Workspace,
  wanted: string,
  source: string,
  overrides: Overrides = {},
  reference: ReferenceTable | null = null,
): Workspace {
  const name = freeName(names(space), wanted);
  return { files: [...space.files, { name, source, overrides, reference }], current: name };
}

/** The workspace with a copy of `name` beside it, open: the same script and the same values
 * under the next free name - or unchanged, when there is no such project. */
export function duplicated(space: Workspace, name: string): Workspace {
  const at = space.files.findIndex((file) => file.name === name);
  const original = space.files[at];
  if (original === undefined) return space;
  const copy = { ...original, name: freeName(names(space), name) };
  return {
    files: [...space.files.slice(0, at + 1), copy, ...space.files.slice(at + 1)],
    current: copy.name,
  };
}

/** The workspace with `name` open - or unchanged, when there is no such project. */
export const switched = (space: Workspace, name: string): Workspace =>
  names(space).includes(name) ? { ...space, current: name } : space;

/** The workspace with `from` called what was typed - or unchanged, when that name will not
 * do. The values go with the script: a project's values file is named for its script, so
 * renaming the one renames the other. */
export function renamed(space: Workspace, from: string, typed: string): Workspace {
  if (nameProblem(names(space), from, typed) !== null) return space;
  const name = normalized(typed);
  return {
    files: space.files.map((file) => (file.name === from ? { ...file, name } : file)),
    current: space.current === from ? name : space.current,
  };
}

/** The workspace without `name`. Deleting the open project opens its neighbour; deleting the
 * last one leaves a new untitled one, from `starter`, since there is always something open. */
export function deleted(space: Workspace, name: string, starter: string): Workspace {
  const at = space.files.findIndex((file) => file.name === name);
  if (at === -1) return space;
  const files = space.files.filter((file) => file.name !== name);
  const neighbour = files[Math.min(at, files.length - 1)];
  if (neighbour === undefined) return single(UNTITLED, starter);
  return { files, current: space.current === name ? neighbour.name : space.current };
}

/** The workspace with an example open. A project already holding that example, untouched, is
 * opened again rather than copied; otherwise the example arrives as a new project, so opening
 * one never costs a person the script they were writing. */
export function withExample(space: Workspace, name: string, source: string): Workspace {
  const same = space.files.find(
    (file) =>
      file.name === name &&
      file.source === source &&
      Object.keys(file.overrides).length === 0 &&
      file.reference === null,
  );
  return same === undefined ? created(space, name, source) : switched(space, same.name);
}

/** The workspace as it is kept: each project's values as the TOML document they are - its
 * `[reference]` table written in beside `[values]` when it has one, so a project opened with
 * a placement still has it after every save, tab switch and reload. */
export const serialized = (space: Workspace): string =>
  JSON.stringify({
    files: space.files.map(({ name, source, overrides, reference }) => ({
      name,
      source,
      values: toml(overrides, name, [], reference),
    })),
    current: space.current,
  });

/** A project's values as the document it shows on its own tab and hands over on download: the
 * same `toml()` `serialized()` writes for keeping, its `[reference]` table threaded through the
 * same way, `order` given when a run has said the script's own declaration order. */
export const document = (project: Project, order: readonly string[] = []): string =>
  toml(project.overrides, project.name, order, project.reference);

/** The values and the `[reference]` table a kept record carries, read the way `values.ts`
 * reads a file.
 *
 * A record kept before the values were a document holds an `overrides` object instead, and
 * is read the way `overrides.ts` read one, so a browser that kept its work under the old shape
 * loses none of it - a shape from before `[reference]` existed, so it never carries one. A
 * record with neither is a project with no values file, which opens on the script's own
 * defaults and no placement; so does one whose document cannot be read, since the script is
 * worth more than the table and there is nobody here to ask.
 */
function fieldsOf(record: Record<string, unknown>): {
  overrides: Overrides;
  reference: ReferenceTable | null;
} {
  const { values, overrides } = record;
  if (typeof values === "string") {
    const found = fromToml(values);
    return found.ok ? { overrides: found.values, reference: found.reference } : { overrides: {}, reference: null };
  }
  return {
    overrides: overrides === undefined ? {} : parsed(JSON.stringify(overrides)),
    reference: null,
  };
}

/** A workspace read back from storage, or `null` when there is none worth keeping.
 *
 * Kept projects are checked one by one: one that is not a name and a script is dropped, a
 * second of the same name is dropped, and its values are read by `valuesOf`. An open project
 * that did not survive gives way to the first that did.
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
  const { files, current } = value as { files?: unknown; current?: unknown };
  if (!Array.isArray(files)) return null;
  const kept: Project[] = [];
  for (const one of files as unknown[]) {
    if (typeof one !== "object" || one === null) continue;
    const record = one as Record<string, unknown>;
    const { name, source } = record;
    if (typeof name !== "string" || typeof source !== "string") continue;
    if (nameProblem([], "", name) !== null || name !== normalized(name)) continue;
    if (kept.some((file) => file.name === name)) continue;
    kept.push({ name, source, ...fieldsOf(record) });
  }
  const first = kept[0];
  if (first === undefined) return null;
  const open = kept.some((file) => file.name === current) ? String(current) : first.name;
  return { files: kept, current: open };
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
  if (source === null) return single(first, examples[first] ?? "", overrides);
  const example = Object.entries(examples).find(([, text]) => text === source)?.[0];
  return single(example ?? UNTITLED, source, overrides);
}
