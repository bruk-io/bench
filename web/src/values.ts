/** A project's values as the document they are kept as: a TOML file with a `[values]` table
 * and, since decision-4, a `[reference]` table beside it.
 *
 * The parameters panel edits a table of scalars by name (`overrides.ts`). This is that table
 * written down the way `tools/build.py` reads it from beside a script on disk - so the file the
 * app keeps, shows and hands over is the same file the command line runs, and a maker can move
 * a project between the two without translating anything. `[reference]` says where a dropped
 * mesh's datum is (`bench.placement`); the app cannot write one today (decision-4's "still the
 * owner's call"), but a file opened with one must keep it through every regeneration, which is
 * why `toml` takes it as an argument rather than this module inventing one.
 *
 * Plain data and functions over it: no DOM and no storage. `toml` writes both tables; `fromToml`
 * reads them back, and reads only what these tables can hold - bare and quoted keys, integers,
 * floats, booleans, basic and literal strings, comments, and - for `[reference]` alone - a
 * triple of numbers - naming the line it cannot read rather than losing the file. Any other
 * table in the document is passed over unread, so a file that has grown a `[[measured]]` table
 * (decision-3) still opens here. What either table *means* is not checked here: a value its
 * field cannot read is refused by the run, by name, as it is from the panel, and a `[reference]`
 * this reads is `bench.placement.placement`'s untrusted mapping, unvalidated until a run or a
 * survey puts it through that reader.
 */
import type { Overrides } from "./overrides";
import type { Scalar } from "./scene";

/** The table a project's values live in - `tools/build.py`'s `VALUES`. */
export const VALUES = "values";

/** The table a project's mesh placement lives in - `tools/build.py`'s `REFERENCE`. */
export const REFERENCE = "reference";

/** The table where a project directory says things about itself that no script can -
 * decision-9's `[project]`, today only `entry`. */
export const PROJECT = "project";

/** The one values document a project directory holds (decision-9), whatever its scripts are
 * called. */
export const BENCH = "bench.toml";

/** A triple of numbers: `[reference]`'s own grammar for `origin`, `up` and `along`, beside
 * the words each may also be (`"low"`, `"+Z"`, …) - `bench.placement.placement` resolves
 * both, this module only reads the shape. */
export type Triple = readonly [number, number, number];

/** A value a `[reference]` table may hold: everything `[values]` can, plus a triple. */
export type ReferenceValue = Scalar | Triple;

/** The `[reference]` table, read or about to be written - untrusted, exactly as
 * `bench.placement.placement` takes it: `origin`, `up`, `along` and `file` are this
 * module's business only as far as their TOML shape, never their meaning. */
export type ReferenceTable = Readonly<Record<string, ReferenceValue>>;

const SCRIPT = ".py";
const DOCUMENT = ".toml";

/** `cabinet.py` as `cabinet`. A name without the extension is its own stem. */
export const stemOf = (script: string): string =>
  script.endsWith(SCRIPT) ? script.slice(0, -SCRIPT.length) : script;

/** The values file beside a script, named for it: `cabinet.py` keeps `cabinet.toml`. */
export const tomlName = (script: string): string => `${stemOf(script)}${DOCUMENT}`;

/** What reading a document came to: its two tables, or why it could not be read.
 *
 * `reference` is `null` for a document with no `[reference]` table in it at all - decision-4's
 * "no table, no move" - and an empty `ReferenceTable` for one that is there but says nothing,
 * which the run itself will refuse for a missing `file`.
 */
export type Read =
  | { readonly ok: true; readonly values: Overrides; readonly reference: ReferenceTable | null }
  | { readonly ok: false; readonly problem: string };

/** What a project's document holds besides `[values]` and `[reference]`: the `[project]`
 * table's `entry`, and everything this version does not read, kept as the lines it was written
 * as so a write puts it back rather than dropping it (task-46 AC#3).
 *
 * - `entry` - the script `[project]` names, or `null` for a document from before there was a
 *   `[project]` table, or one whose `entry` is not a string.
 * - `root` - key lines above the first table header, which TOML only allows there.
 * - `project` - every other line of `[project]`, a key some later version wrote.
 * - `tables` - every other table, its header included - a `[[measured]]` (decision-3), or
 *   whatever comes next.
 *
 * Comments inside a table this does read are not kept: that table is regenerated on every
 * write, as `[values]` always has been.
 */
export interface Kept {
  readonly entry: string | null;
  readonly root: readonly string[];
  readonly project: readonly string[];
  readonly tables: readonly string[];
  /** A document `fromToml` could not read at all - a value this version has no reader for, a
   * hand edit with a typo - kept whole, with why, so it is never regenerated over: nothing
   * above can say which of its lines it would be losing. Absent for one that was read. */
  readonly unreadable?: { readonly text: string; readonly problem: string };
}

/** A document with nothing in it but what this version reads. */
export const NOTHING_KEPT: Kept = { entry: null, root: [], project: [], tables: [] };

// ---- writing --------------------------------------------------------------------------

const BARE_KEY = /^[A-Za-z0-9_-]+$/;

/** `text` as a TOML basic string, every character it cannot hold escaped. */
function quoted(text: string): string {
  let out = '"';
  for (const char of text) {
    const code = char.codePointAt(0) ?? 0;
    if (char === '"') out += '\\"';
    else if (char === "\\") out += "\\\\";
    else if (char === "\n") out += "\\n";
    else if (char === "\t") out += "\\t";
    else if (char === "\r") out += "\\r";
    else if (code < 0x20 || code === 0x7f) out += `\\u${code.toString(16).padStart(4, "0")}`;
    else out += char;
  }
  return `${out}"`;
}

/** One value as TOML writes it. A whole number is written as an integer whatever field it is
 * for: the run coerces to the field's own type, so `3` lands in a float field as `3.0`. */
function literal(value: Scalar): string {
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  return quoted(value);
}

/** A `[reference]` value as TOML writes it: a triple as `[x, y, z]`, everything else as
 * `literal` already writes it. */
function referenceLiteral(value: ReferenceValue): string {
  // `typeof`, not `Array.isArray`: a readonly tuple does not narrow out of the union through
  // `isArray`'s own `arg is any[]` guard, since a `readonly` array is not one of those.
  return typeof value === "object" ? `[${value.map(String).join(", ")}]` : literal(value);
}

/** The names of `table` in the order to write them: the ones in `order` first, in that order,
 * then the rest as the table has them. `order` is the script's declaration order when a run
 * has said it, so the file reads like the dataclass does - and, for a `[reference]` table,
 * `file`, `origin`, `up`, `along`, so it reads the way decision-4's own example does. */
function ordered<T>(table: Readonly<Record<string, T>>, order: readonly string[]): string[] {
  const set = new Set(Object.keys(table));
  const first = order.filter((name) => set.has(name));
  const rest = Object.keys(table).filter((name) => !order.includes(name));
  return [...first, ...rest];
}

const REFERENCE_ORDER = ["file", "origin", "up", "along"];

/** `table` as the values file of `script`, its `[reference]` table kept beside it when there
 * is one.
 *
 * One `[values]` table, one line per value; an empty table is a file that says every value is
 * the script's own, which is a project with no values file beside it. The comment names the
 * script so the file still says what it is for when it is read somewhere else. `reference` is
 * written exactly as read - the app cannot compose one yet (decision-4) - so a project opened
 * with a placement still has it after every edit to `[values]` regenerates this file.
 */
export function toml(
  table: Overrides,
  script: string,
  order: readonly string[] = [],
  reference: ReferenceTable | null = null,
  kept: Kept = NOTHING_KEPT,
): string {
  const lines = [`# The values ${script} builds with. A field left out keeps the script's own default.`];
  lines.push(...kept.root);
  if (kept.entry !== null || kept.project.length > 0) {
    lines.push(`[${PROJECT}]`);
    if (kept.entry !== null) lines.push(`entry = ${quoted(kept.entry)}`);
    lines.push(...kept.project, "");
  }
  lines.push(`[${VALUES}]`);
  for (const name of ordered(table, order)) {
    const value = table[name];
    if (value === undefined) continue;
    const key = BARE_KEY.test(name) ? name : quoted(name);
    lines.push(`${key} = ${literal(value)}`);
  }
  if (reference !== null) {
    lines.push("", `[${REFERENCE}]`);
    for (const name of ordered(reference, REFERENCE_ORDER)) {
      const value = reference[name];
      if (value === undefined) continue;
      const key = BARE_KEY.test(name) ? name : quoted(name);
      lines.push(`${key} = ${referenceLiteral(value)}`);
    }
  }
  if (kept.tables.length > 0) lines.push("", ...trimmed(kept.tables));
  return `${lines.join("\n")}\n`;
}

/** `lines` without the blank lines at either end - a kept table is put back with exactly one
 * blank line before it, however many it was read with, so a file does not grow a line on
 * every write. */
function trimmed(lines: readonly string[]): readonly string[] {
  let start = 0;
  let end = lines.length;
  while (start < end && (lines[start] ?? "").trim() === "") start += 1;
  while (end > start && (lines[end - 1] ?? "").trim() === "") end -= 1;
  return lines.slice(start, end);
}

// ---- reading --------------------------------------------------------------------------

const HEADER = /^\[\[?\s*([^\]]*?)\s*\]?\]$/;
const BARE = /^[A-Za-z0-9_-]+/;
const INTEGER = /^[+-]?(?:0|[1-9](?:_?\d)*)$/;
const FLOAT = /^[+-]?(?:0|[1-9](?:_?\d)*)(?:\.\d(?:_?\d)*)?(?:[eE][+-]?\d(?:_?\d)*)?$/;
const NOT_A_NUMBER = /^[+-]?(?:inf|nan)$/;

const ESCAPES: Readonly<Record<string, string>> = {
  b: "\b",
  t: "\t",
  n: "\n",
  f: "\f",
  r: "\r",
  '"': '"',
  "\\": "\\",
};

/** A basic string's body, its escapes read - or `null` for an escape that is not one. */
function unescaped(body: string): string | null {
  let out = "";
  for (let at = 0; at < body.length; at += 1) {
    const char = body[at] ?? "";
    if (char !== "\\") {
      out += char;
      continue;
    }
    const next = body[at + 1] ?? "";
    const simple = ESCAPES[next];
    if (simple !== undefined) {
      out += simple;
      at += 1;
      continue;
    }
    const width = next === "u" ? 4 : next === "U" ? 8 : 0;
    const hex = body.slice(at + 2, at + 2 + width);
    if (width === 0 || hex.length !== width || !/^[0-9A-Fa-f]+$/.test(hex)) return null;
    out += String.fromCodePoint(Number.parseInt(hex, 16));
    at += 1 + width;
  }
  return out;
}

/** The quoted string `text` opens with, and what follows it - or `null` when it does not open
 * with a string this reads (a multi-line string is not one). */
function stringAt(text: string): { value: string; rest: string } | null {
  const quote = text[0];
  if (quote !== '"' && quote !== "'") return null;
  if (text.startsWith(quote.repeat(3))) return null;
  let at = 1;
  while (at < text.length) {
    const char = text[at];
    if (char === "\\" && quote === '"') {
      at += 2;
      continue;
    }
    if (char === quote) {
      const body = text.slice(1, at);
      const value = quote === '"' ? unescaped(body) : body;
      return value === null ? null : { value, rest: text.slice(at + 1) };
    }
    at += 1;
  }
  return null;
}

/** The key `text` opens with, and what follows it. */
function keyAt(text: string): { key: string; rest: string } | null {
  const found = stringAt(text);
  if (found !== null) return { key: found.value, rest: found.rest };
  const bare = BARE.exec(text);
  if (bare === null) return null;
  return { key: bare[0], rest: text.slice(bare[0].length) };
}

/** Whether `text`, after a value, is nothing or a comment - which is all TOML allows there. */
const trailing = (text: string): boolean => text.trim() === "" || text.trim().startsWith("#");

/** The scalar `text` is, with whatever follows it - or `null` for anything this cannot read. */
function valueAt(text: string): { value: Scalar; rest: string } | null {
  const string = stringAt(text);
  if (string !== null) return string;
  // A bare value runs to the end of the line or to a comment.
  const end = text.search(/\s#|^#/);
  const word = (end === -1 ? text : text.slice(0, end)).trim();
  const rest = end === -1 ? "" : text.slice(end);
  if (word === "true") return { value: true, rest };
  if (word === "false") return { value: false, rest };
  if (NOT_A_NUMBER.test(word)) return null;
  if (INTEGER.test(word) || FLOAT.test(word)) {
    const number = Number(word.replaceAll("_", ""));
    return Number.isFinite(number) ? { value: number, rest } : null;
  }
  return null;
}

const NUMBER = /^[+-]?(?:0|[1-9](?:_?\d)*)(?:\.\d(?:_?\d)*)?(?:[eE][+-]?\d(?:_?\d)*)?/;

/** The number `text` opens with, and what follows it - or `null` when it does not. Unlike
 * `valueAt`'s bare word, this does not run to a comment: a number inside `[…]` is bounded by
 * a comma or the closing bracket, and nothing else is legal there. */
function numberAt(text: string): { value: number; rest: string } | null {
  const match = NUMBER.exec(text);
  if (match === null) return null;
  const number = Number(match[0].replaceAll("_", ""));
  return Number.isFinite(number) ? { value: number, rest: text.slice(match[0].length) } : null;
}

/** The triple `text` opens with - `[x, y, z]`, `origin`, `up` and `along`'s own grammar - and
 * what follows it, or `null` for anything else: not three numbers, or more than three. A
 * trailing comma before `]` is allowed, as TOML's own arrays allow it. */
function tripleAt(text: string): { value: Triple; rest: string } | null {
  if (!text.startsWith("[")) return null;
  let rest = text.slice(1).trimStart();
  const found: number[] = [];
  while (found.length < 3) {
    const number = numberAt(rest);
    if (number === null) return null;
    found.push(number.value);
    rest = number.rest.trimStart();
    if (found.length < 3) {
      if (!rest.startsWith(",")) return null;
      rest = rest.slice(1).trimStart();
    }
  }
  if (rest.startsWith(",")) rest = rest.slice(1).trimStart();
  if (!rest.startsWith("]")) return null;
  const [x, y, z] = found as [number, number, number];
  return { value: [x, y, z], rest: rest.slice(1) };
}

/** The `[reference]` value `text` is - everything `valueAt` reads, plus a triple - with
 * whatever follows it, or `null` for anything else. */
function referenceValueAt(text: string): { value: ReferenceValue; rest: string } | null {
  return tripleAt(text) ?? valueAt(text);
}

/** One `key = value` line of `table`, read by `reader` - or the problem naming `where` and
 * the key, in `expected`'s words, when it cannot be. Shared by `[values]` and `[reference]`,
 * which differ only in what a value there may be. */
function keyValueAt<T>(
  line: string,
  where: string,
  reader: (text: string) => { value: T; rest: string } | null,
  expected: string,
): { key: string; value: T } | { problem: string } {
  const key = keyAt(line);
  if (key === null) return { problem: `${where} is not a key and a value` };
  const after = key.rest.trimStart();
  if (!after.startsWith("=")) return { problem: `${where} has no "=" after ${key.key}` };
  const read = reader(after.slice(1).trimStart());
  if (read === null || !trailing(read.rest)) {
    return { problem: `${where}: ${key.key} is not ${expected}` };
  }
  return { key: key.key, value: read.value };
}

/** The `[values]` and `[reference]` tables of a project's TOML, as the panel's table and the
 * placement `bench.placement.placement` will read.
 *
 * A document with no `[values]` in it is a project with no values: `ok`, and empty. A document
 * with no `[reference]` in it is a project with no placement: `ok`, and `null` - decision-4's
 * "no table, no move". A line this cannot read as a key and a value is a problem naming the
 * line - and the reasons are in `fromToml`'s own words, since neither a run nor a survey ever
 * sees this file, only the tables.
 */
export function fromToml(text: string): Read {
  const values: Record<string, Scalar> = {};
  const reference: Record<string, ReferenceValue> = {};
  let sawReference = false;
  let table: string | null = null;
  const lines = text.split(/\r?\n/);
  for (const [index, raw] of lines.entries()) {
    const line = raw.trim();
    const where = `line ${index + 1}`;
    if (line === "" || line.startsWith("#")) continue;
    const header = HEADER.exec(line);
    if (header !== null) {
      table = header[1] ?? "";
      if (table === REFERENCE) sawReference = true;
      continue;
    }
    if (table !== VALUES && table !== REFERENCE) continue; // the root table and the rest are not ours
    const into = table === VALUES ? values : reference;
    const read =
      table === VALUES
        ? keyValueAt(line, where, valueAt, "a number, a string or true/false")
        : keyValueAt(line, where, referenceValueAt, "a number, a string, true/false or a triple");
    if ("problem" in read) return { ok: false, problem: read.problem };
    if (Object.hasOwn(into, read.key)) {
      return { ok: false, problem: `${where} sets ${read.key} a second time` };
    }
    into[read.key] = read.value;
  }
  return { ok: true, values, reference: sawReference ? reference : null };
}

/** What `fromToml` passes over in `text`, kept: `[project]`'s `entry`, and every line of every
 * table this version does not read, in the order it came.
 *
 * Never a problem: a line here is either `entry`, read when it is a string and kept as it was
 * when not, or somebody else's, kept without being read. That is the whole of the
 * compatibility promise - a file a later version wrote opens here, and is written back with
 * what this version could not read still in it. Comments above the first table are not kept,
 * because `toml` writes its own there and would otherwise grow one on every write.
 */
export function keptOf(text: string): Kept {
  let entry: string | null = null;
  const root: string[] = [];
  const project: string[] = [];
  const tables: string[] = [];
  let table: string | null = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    const header = HEADER.exec(line);
    if (header !== null) {
      table = header[1] ?? "";
      if (table !== VALUES && table !== REFERENCE && table !== PROJECT) tables.push(raw);
      continue;
    }
    if (table === VALUES || table === REFERENCE) continue;
    if (table === null) {
      if (line !== "" && !line.startsWith("#")) root.push(raw);
      continue;
    }
    if (table !== PROJECT) {
      tables.push(raw);
      continue;
    }
    if (line === "" || line.startsWith("#")) continue;
    const read = keyValueAt(line, "", valueAt, "");
    if (entry === null && !("problem" in read) && read.key === "entry" && typeof read.value === "string") {
      entry = read.value;
      continue;
    }
    project.push(raw);
  }
  return { entry, root, project, tables };
}
