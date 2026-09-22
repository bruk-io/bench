/** The override table: the values a person has set in the parameters panel, by name.
 *
 * Plain data and functions over it. The page owns the one table there is and hands it down to
 * the panel; the panel only says what was edited. It used to live in two places - the panel
 * and the host - and a scene arriving from a run that started before an edge-of-debounce edit
 * put the stale copy back, so the widget and the cut files disagreed with no error.
 */
import type { ParamView, Scalar } from "./scene";

export type Overrides = Readonly<Record<string, Scalar>>;

const isScalar = (value: unknown): value is Scalar =>
  typeof value === "boolean" || typeof value === "number" || typeof value === "string";

/** A table read back from storage, keeping only what could be one: an object of scalars. */
export function parsed(said: string | null): Overrides {
  if (said === null) return {};
  let value: unknown;
  try {
    value = JSON.parse(said);
  } catch {
    return {};
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value).filter(([, one]) => isScalar(one)));
}

/** The table with one more value set - a new table, the old one untouched. */
export const withOverride = (table: Overrides, name: string, value: Scalar): Overrides => ({
  ...table,
  [name]: value,
});

/** The table without the names nobody declares - or the very same table when nothing goes.
 *
 * A remembered override outlives the script that asked for it: rename or delete a settings
 * field and the old name would sit in the table for ever, travelling to every later run. An
 * empty declaration list prunes nothing, since a script with no parameters shows a part
 * directly and has nothing to prune against. */
export function declaredOnly(table: Overrides, params: readonly ParamView[]): Overrides {
  if (params.length === 0) return table;
  const declared = new Set(params.map((one) => one.name));
  const kept = Object.entries(table).filter(([name]) => declared.has(name));
  return kept.length === Object.keys(table).length ? table : Object.fromEntries(kept);
}

/** The table with each value replaced by what the run built from it - or the very same table
 * when the run built every one as it was sent.
 *
 * `configured` holds a number outside its field's range at the nearer end and rounds one an
 * int field was sent, and the scene's `values` say what was actually built. A file that said
 * `units_x = 9` against a run that built 7 would be a quiet lie, so the run's answer is
 * written back: the rule stays in `params.py`, once, and nothing here works it out again. A
 * name the run does not report - a script that declares no parameters - keeps what it had.
 */
export function asBuilt(table: Overrides, values: Readonly<Record<string, Scalar>>): Overrides {
  const entries = Object.entries(table).map(
    ([name, one]) => [name, Object.hasOwn(values, name) ? (values[name] ?? one) : one] as const,
  );
  return entries.some(([name, one]) => one !== table[name]) ? Object.fromEntries(entries) : table;
}
