/** The contract of `bench.script` - see DESIGN.md, "script.py".
 *
 * Every optional-looking field of a param is always present and may be `null`; a lettering's
 * `ref` may be `null`; an error's `line` may be `null`.
 *
 * A scene arrives in two pieces: JSON, and the buffers every part's long lists were taken out
 * into (`bench.transport.scene_wire`). In the JSON a mesh's `positions` and `ref_index`, and a
 * part's marks' `segments` and `ref_index`, are the numbers of the buffers that hold them;
 * `received` checks both pieces and puts them back together, and everything past it only ever
 * sees a whole scene.
 */

export type Scalar = boolean | number | string;

export type ParamKind = "bool" | "int" | "float" | "str" | "choice";

export interface ParamView {
  readonly name: string;
  readonly label: string;
  readonly kind: ParamKind;
  readonly default: Scalar;
  readonly min: number | null;
  readonly max: number | null;
  readonly step: number | null;
  readonly choices: readonly Scalar[] | null;
}

export interface StockView {
  readonly thickness: number;
  readonly material: string;
  readonly kerf: number;
}

/** A body ready to draw. `positions` is nine numbers per triangle - its three corners,
 * already placed on the stage - and `ref_index` is one number per triangle: the face it lies
 * on, as `refs[ref_index - 1]`, or `0` for a triangle of no named face, which is the part
 * itself. Nothing here needs working out before it is handed to the renderer. */
export interface MeshView {
  readonly positions: Float32Array;
  readonly ref_index: Uint32Array;
  readonly refs: readonly string[];
}

/** The wires engraved on a plate: `segments` is six numbers per line segment, both ends
 * already placed just clear of the top, and `ref_index` one number per segment, counted as a
 * mesh's are. */
export interface MarksView {
  readonly segments: Float32Array;
  readonly ref_index: Uint32Array;
  readonly refs: readonly string[];
}

/** A line of engraved text and the four corners, twelve numbers already placed, of the box it
 * fills on a plate's top: along the baseline, then back along the cap height. */
export interface LetteringView {
  readonly text: string;
  readonly ref: string | null;
  readonly corners: readonly number[];
}

/** The floor under the work: its width, how many cells across, and its middle `x, y`. */
export interface GridView {
  readonly size: number;
  readonly divisions: number;
  readonly centre: readonly number[];
}

/** Where the bodies stand: the box they fill, `x0, y0, z0, x1, y1, z1`, and the floor. */
export interface StageView {
  readonly bounds: readonly number[];
  readonly grid: GridView;
}

export type Severity = "error" | "warning" | "unchecked";

/** One thing a check found: which check, what it says, how much it matters, the refs to
 * highlight and the line of the script that asked. `unchecked` is not a pass - it is a
 * question nothing in this run could answer. */
export interface ViolationView {
  readonly check: string;
  readonly message: string;
  readonly severity: Severity;
  readonly refs: readonly string[];
  readonly line: number | null;
}

/** One part: what to call it, how many to cut, what it is made of, and its body - a laser
 * part's plate or a printed part's solid - with what is engraved on it. `mesh` is `null` for a
 * part with no body to draw, and `marks` for a part with no engraved wire. */
export interface PartView {
  readonly ref: string;
  readonly label: string;
  readonly qty: number;
  readonly stock: StockView;
  readonly process: string;
  readonly bbox: readonly number[];
  readonly mesh: MeshView | null;
  readonly marks: MarksView | null;
  readonly lettering: readonly LetteringView[];
}

/** What a run amounts to, counted in Python so the app only words it: what was made and
 * nested, what the checks found and the line of the first error, and how many parts have a
 * body to draw and how many do not. */
export interface SummaryView {
  readonly parts: number;
  readonly sheets: number;
  readonly errors: number;
  readonly warnings: number;
  readonly error_line: number | null;
  readonly solid: number;
  readonly unbuilt: number;
}

/** One nested sheet: its cut file's SVG, and the same drawing with lines wide enough to see
 * once it is shrunk to a thumbnail - a cutter's hairline at that size is no line at all. */
export interface SheetView {
  readonly name: string;
  readonly thickness: number;
  readonly svg: string;
  readonly preview: string;
  readonly parts: readonly string[];
}

export interface ErrorView {
  readonly message: string;
  readonly line: number | null;
  readonly traceback: string;
}

export interface OkScene {
  readonly ok: true;
  readonly params: readonly ParamView[];
  readonly values: Readonly<Record<string, Scalar>>;
  readonly parts: readonly PartView[];
  readonly stage: StageView;
  readonly summary: SummaryView;
  readonly refs: readonly string[];
  readonly sheets: readonly SheetView[];
  readonly files: Readonly<Record<string, string>>;
  readonly violations: readonly ViolationView[];
  readonly warnings: readonly string[];
  readonly stdout: string;
  readonly stderr: string;
  /** A body somebody else made, handed to the run rather than built by it, so the view can
   * stand the work against the thing it is copying. It names no faces - every triangle of it
   * indexes nothing - so it is drawn and never selected. `null` when nothing was offered. */
  readonly reference: MeshView | null;
}

export interface ErrorScene {
  readonly ok: false;
  readonly error: ErrorView;
  readonly stdout: string;
  readonly stderr: string;
}

export type Scene = OkScene | ErrorScene;

// ---- the worker boundary -----------------------------------------------------
//
// Everything above is a promise about what crossed a `postMessage` from a Python interpreter
// in another thread. The predicates below are where that promise is checked: they look at
// exactly the keys and kinds this app reads, so a payload that would have half-updated the UI
// and then thrown mid-render is rejected as a failure instead.

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isScalar = (value: unknown): value is Scalar =>
  typeof value === "boolean" || typeof value === "number" || typeof value === "string";

const isText = (value: unknown): value is string => typeof value === "string";

const isOptionalText = (value: unknown): boolean => value === null || typeof value === "string";

const isNumber = (value: unknown): value is number => typeof value === "number";

const isList = (value: unknown): value is unknown[] => Array.isArray(value);

const isTextList = (value: unknown): value is string[] => isList(value) && value.every(isText);

const isTextTable = (value: unknown): boolean =>
  isObject(value) && Object.values(value).every(isText);

const isNumbers = (value: unknown, count: number): boolean =>
  isList(value) && value.length === count && value.every(isNumber);

/** A buffer's number in the list that came with the JSON. */
const isSlot = (value: unknown): value is number => Number.isInteger(value) && Number(value) >= 0;

const SUMMARY_COUNTS = ["parts", "sheets", "errors", "warnings", "solid", "unbuilt"] as const;

/** The first thing wrong with what a run amounts to, or `null`. */
function summaryProblem(value: unknown): string | null {
  if (!isObject(value)) return "summary is not an object";
  for (const field of SUMMARY_COUNTS) {
    if (!Number.isInteger(value[field])) return `summary.${field} is not a whole number`;
  }
  if (value["error_line"] !== null && !isNumber(value["error_line"])) {
    return "summary.error_line is not a number or null";
  }
  return null;
}

/** The first thing wrong with a part's long lists as the JSON carries them - its mesh, whose
 * lists are `positions` and `ref_index`, or its marks, whose are `segments` and `ref_index` -
 * or `null`. A part with nothing to draw has `null` here, and that is not a problem. */
function listsProblem(value: unknown, where: string, first: "positions" | "segments"): string | null {
  if (value === null) return null;
  if (!isObject(value)) return `${where} is not an object or null`;
  if (!isSlot(value[first])) return `${where}.${first} is not a buffer number`;
  if (!isSlot(value["ref_index"])) return `${where}.ref_index is not a buffer number`;
  if (!isTextList(value["refs"])) return `${where}.refs is not strings`;
  return null;
}

/** The first thing wrong with where the bodies stand, or `null`. */
function stageProblem(value: unknown): string | null {
  if (!isObject(value)) return "stage is not an object";
  if (!isNumbers(value["bounds"], 6)) return "stage.bounds is not six numbers";
  const floor = value["grid"];
  if (!isObject(floor)) return "stage.grid is not an object";
  if (!isNumber(floor["size"]) || !isNumber(floor["divisions"])) {
    return "stage.grid has no numeric size and divisions";
  }
  if (!isNumbers(floor["centre"], 2)) return "stage.grid.centre is not two numbers";
  return null;
}

/** The first thing wrong with one violation, or `null`. */
function violationProblem(value: unknown, at: number): string | null {
  if (!isObject(value)) return `violations[${at}] is not an object`;
  if (!isText(value["check"])) return `violations[${at}].check is not a string`;
  const where = `violations[${at}] (${value["check"]})`;
  if (!isText(value["message"])) return `${where}.message is not a string`;
  if (!isText(value["severity"])) return `${where}.severity is not a string`;
  if (!isTextList(value["refs"])) return `${where}.refs is not an array of strings`;
  if (value["line"] !== null && !isNumber(value["line"])) {
    return `${where}.line is not a number or null`;
  }
  return null;
}

/** The first thing wrong with one part, or `null`. */
function partProblem(value: unknown, at: number): string | null {
  if (!isObject(value)) return `parts[${at}] is not an object`;
  if (!isText(value["ref"])) return `parts[${at}].ref is not a string`;
  const where = `parts[${at}] (${value["ref"]})`;
  if (!isNumber(value["qty"])) return `${where}.qty is not a number`;
  if (!isNumbers(value["bbox"], 4)) return `${where}.bbox is not four numbers`;
  if (!isObject(value["stock"]) || !isNumber(value["stock"]["thickness"])) {
    return `${where}.stock has no numeric thickness`;
  }
  if (!isText(value["stock"]["material"])) return `${where}.stock.material is not a string`;
  if (!isList(value["lettering"])) return `${where}.lettering is not an array`;
  for (const [index, one] of value["lettering"].entries()) {
    if (!isObject(one)) return `${where}.lettering[${index}] is not an object`;
    if (!isText(one["text"])) return `${where}.lettering[${index}].text is not a string`;
    if (!isOptionalText(one["ref"])) return `${where}.lettering[${index}].ref is not a string or null`;
    if (!isNumbers(one["corners"], 12)) return `${where}.lettering[${index}].corners is not twelve numbers`;
  }
  return (
    listsProblem(value["mesh"], `${where}.mesh`, "positions") ??
    listsProblem(value["marks"], `${where}.marks`, "segments")
  );
}

/** The first thing wrong with one parameter declaration, or `null`. */
function paramProblem(value: unknown, at: number): string | null {
  if (!isObject(value)) return `params[${at}] is not an object`;
  if (!isText(value["name"])) return `params[${at}].name is not a string`;
  const where = `params[${at}] (${value["name"]})`;
  if (!isText(value["label"])) return `${where}.label is not a string`;
  if (!isText(value["kind"])) return `${where}.kind is not a string`;
  if (!isScalar(value["default"])) return `${where}.default is not a scalar`;
  for (const field of ["min", "max", "step"] as const) {
    if (value[field] !== null && !isNumber(value[field])) {
      return `${where}.${field} is not a number or null`;
    }
  }
  const choices = value["choices"];
  if (choices !== null && !(isList(choices) && choices.every(isScalar))) {
    return `${where}.choices is not an array of scalars or null`;
  }
  return null;
}

/** The first thing wrong with one sheet, or `null`. */
function sheetProblem(value: unknown, at: number): string | null {
  if (!isObject(value)) return `sheets[${at}] is not an object`;
  if (!isText(value["name"])) return `sheets[${at}].name is not a string`;
  const where = `sheets[${at}] (${value["name"]})`;
  if (!isNumber(value["thickness"])) return `${where}.thickness is not a number`;
  if (!isText(value["svg"])) return `${where}.svg is not a string`;
  if (!isText(value["preview"])) return `${where}.preview is not a string`;
  if (!isTextList(value["parts"])) return `${where}.parts is not an array of strings`;
  return null;
}

/** The first thing wrong with a scene that claims `ok: true`, or `null`. */
function okProblem(value: unknown): string | null {
  if (!isObject(value)) return "not an object";
  if (value["ok"] !== true) return 'no "ok": true';
  if (!isList(value["params"])) return "params is not an array";
  for (const [at, param] of value["params"].entries()) {
    const problem = paramProblem(param, at);
    if (problem !== null) return problem;
  }
  if (!isObject(value["values"])) return "values is not an object";
  if (!isList(value["parts"])) return "parts is not an array";
  for (const [at, part] of value["parts"].entries()) {
    const problem = partProblem(part, at);
    if (problem !== null) return problem;
  }
  const stage = stageProblem(value["stage"]);
  if (stage !== null) return stage;
  const summary = summaryProblem(value["summary"]);
  if (summary !== null) return summary;
  if (!isTextList(value["refs"])) return "refs is not an array of strings";
  if (!isList(value["sheets"])) return "sheets is not an array";
  for (const [at, sheet] of value["sheets"].entries()) {
    const problem = sheetProblem(sheet, at);
    if (problem !== null) return problem;
  }
  if (!isTextTable(value["files"])) return "files is not an object of strings";
  if (!isList(value["violations"])) return "violations is not an array";
  for (const [at, found] of value["violations"].entries()) {
    const problem = violationProblem(found, at);
    if (problem !== null) return problem;
  }
  if (!isTextList(value["warnings"])) return "warnings is not an array of strings";
  if (!isText(value["stdout"])) return "stdout is not a string";
  if (!isText(value["stderr"])) return "stderr is not a string";
  // Required and nullable, like every other field here: a scene always carries the key, and
  // `null` is how it says there is no body to stand behind the work. An absent key is a
  // scene from something that is not this contract, and saying so is the whole job.
  if (!("reference" in value)) return "reference is absent";
  if (value["reference"] !== null) {
    const problem = listsProblem(value["reference"], "reference", "positions");
    if (problem !== null) return problem;
  }
  return null;
}

/** The first thing wrong with a scene that claims `ok: false`, or `null`. */
function errorProblem(value: unknown): string | null {
  if (!isObject(value)) return "not an object";
  if (value["ok"] !== false) return 'no "ok": false';
  const view = value["error"];
  if (!isObject(view)) return "error is not an object";
  if (!isText(view["message"])) return "error.message is not a string";
  if (view["line"] !== null && !isNumber(view["line"])) return "error.line is not a number or null";
  if (!isText(view["traceback"])) return "error.traceback is not a string";
  if (!isText(value["stdout"])) return "stdout is not a string";
  if (!isText(value["stderr"])) return "stderr is not a string";
  return null;
}

/** Why the JSON half of a scene is not one, in one clause, or `null` when it is one. */
function sceneProblem(value: unknown): string | null {
  if (!isObject(value)) return "not an object";
  if (value["ok"] === true) return okProblem(value);
  if (value["ok"] === false) return errorProblem(value);
  return `"ok" is ${JSON.stringify(value["ok"]) ?? "absent"}, not a boolean`;
}

/** A part's long lists with their buffers put back - `per` numbers of the float buffer to
 * each entry of the index - or why they do not fit. */
function listsWith(
  wire: Record<string, unknown>,
  where: string,
  buffers: readonly unknown[],
  first: "positions" | "segments",
  per: number,
): { readonly floats: Float32Array; readonly index: Uint32Array; readonly refs: string[] } | string {
  const floats = buffers[Number(wire[first])];
  const index = buffers[Number(wire["ref_index"])];
  const refs = wire["refs"] as string[];
  if (!(floats instanceof Float32Array)) return `${where}.${first} is not a Float32Array`;
  if (!(index instanceof Uint32Array)) return `${where}.ref_index is not a Uint32Array`;
  if (floats.length !== per * index.length) {
    return `${where} has ${floats.length / per} entries of numbers and ${index.length} of refs`;
  }
  if (index.some((one) => one > refs.length)) return `${where} names a ref it does not carry`;
  return { floats, index, refs };
}

/** A scene from its two halves - the JSON and the buffers its long lists were taken out into -
 * or the one clause saying why they do not make one. */
export function received(
  value: unknown,
  buffers: unknown,
): { readonly scene: Scene } | { readonly problem: string } {
  const problem = sceneProblem(value);
  if (problem !== null) return { problem };
  const wire = value as Record<string, unknown>;
  if (wire["ok"] !== true) return { scene: value as ErrorScene };
  const given = isList(buffers) ? buffers : [];
  const parts: Record<string, unknown>[] = [];
  for (const [at, one] of (wire["parts"] as Record<string, unknown>[]).entries()) {
    const where = `parts[${at}] (${String(one["ref"])})`;
    let mesh: MeshView | null = null;
    let marks: MarksView | null = null;
    if (one["mesh"] !== null) {
      const lists = listsWith(one["mesh"] as Record<string, unknown>, `${where}.mesh`, given, "positions", 9);
      if (typeof lists === "string") return { problem: lists };
      mesh = { positions: lists.floats, ref_index: lists.index, refs: lists.refs };
    }
    if (one["marks"] !== null) {
      const lists = listsWith(one["marks"] as Record<string, unknown>, `${where}.marks`, given, "segments", 6);
      if (typeof lists === "string") return { problem: lists };
      marks = { segments: lists.floats, ref_index: lists.index, refs: lists.refs };
    }
    parts.push({ ...one, mesh, marks });
  }
  let reference: MeshView | null = null;
  if (wire["reference"] !== null) {
    const lists = listsWith(
      wire["reference"] as Record<string, unknown>,
      "reference",
      given,
      "positions",
      9,
    );
    if (typeof lists === "string") return { problem: lists };
    reference = { positions: lists.floats, ref_index: lists.index, refs: lists.refs };
  }
  return { scene: { ...wire, parts, reference } as unknown as OkScene };
}
