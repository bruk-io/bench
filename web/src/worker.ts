/** The Python side, off the main thread - and the solid modeller beside it.
 *
 * Boots Pyodide from the self-hosted copy under `<base>/pyodide/`, writes the bundled
 * `bench` package into `/lib` of its filesystem, and answers one run at a time. A run
 * request that arrives while another is in flight replaces any queued one: the editor
 * only ever wants the latest text.
 *
 * **Both runtimes live here, in one thread, and that is the whole design.** Manifold's WASM
 * is loaded from `<base>/manifold/` into this same worker and bound as a table of handles
 * (`modeller.ts`), and handed to `bench.script.run` wrapped in `JsKernel`, which is the kernel:
 * Python walks the tree, names every face and calls the modeller *synchronously* - no
 * message, no await - so a check written in Python measures a body built in WASM without
 * either side knowing it crossed a language.
 *
 * **Telemetry goes to the page.** The worker keeps no sink of its own: its own spans and log
 * records, and Python's - `bench`'s `logging` records and the spans `bench.telemetry` times -
 * are posted to the page as they happen, because the page's timeline is the one a collector
 * watches. Python reaches them through the two plain functions in `python`, below.
 *
 * The boot is raced against a timeout because `loadPyodide` hangs rather than rejects on a
 * truncated or mistyped wasm, and a boot that loses the race is not remembered: the next
 * run tries again, which is what a person who reloads a flaky network expects. The modeller
 * is not raced and not required: if it will not load, the run is given no kernel and the
 * scene comes back with `mesh: null` on every part - every ref, parameter and cut sheet
 * still there, which is the whole of what a laser part needs.
 */
import { type Modeller, bind, load as loadManifold } from "./modeller";
import { type Attributes, attach, isLevel, log, logged, spanned, timed, timedAsync } from "./telemetry";

import { PY_SOURCES } from "./generated/pysources";

interface WorkerScope {
  postMessage(message: unknown, transfer?: Transferable[]): void;
  addEventListener(type: "message", listener: (event: MessageEvent) => void): void;
}

const scope = self as unknown as WorkerScope;

attach({
  log: (record) => scope.postMessage({ type: "telemetry", log: record }),
  span: (record) => scope.postMessage({ type: "telemetry", span: record }),
});

/** Just enough of Pyodide to boot it, fill its filesystem and call into it. */
interface PyodideFS {
  mkdir(path: string): void;
  writeFile(path: string, data: string, options?: { encoding?: string }): void;
}

interface PyodideModule {
  FS: PyodideFS;
  runPython(code: string): unknown;
}

type LoadPyodide = (options: {
  indexURL: string;
  stdout?: (text: string) => void;
  stderr?: (text: string) => void;
}) => Promise<PyodideModule>;

export interface RunRequest {
  id: number;
  type: "run";
  source: string;
  overrides: Record<string, unknown>;
  /** A body dropped on the view, as a base64 binary STL, bound into the script as
   * `reference`. Absent when nothing was dropped - and absent rather than null, for the
   * reason the `Runner` type gives below. */
  stl?: string;
  /** The open project's `[reference]` table, as JSON - present only when `stl` is the body
   * that table's own `file` names, so the mesh is placed before the script sees it. Absent
   * for the same reason `stl` can be: decision-4's "no table, no move". */
  table?: string;
  /** The open project's other scripts, as JSON (`{name: text}`) - absent for a project of one
   * script, which is most of them (task-50). `bench.worker.start`'s runner mounts them for
   * the source to import; the app never mounts them itself. */
  modules?: string;
}

/** Measure a body dropped on the view and write the survey out as a report. Asked once per
 * drop rather than once per run: the body does not change under the keystrokes that rerun
 * the script, and a real export of twenty thousand triangles takes seconds to measure. */
export interface SurveyRequest {
  id: number;
  type: "survey";
  /** The body, as a base64 binary STL - the same text the run is handed as `stl`. */
  stl: string;
  /** The `[reference]` table this body is placed by, as JSON - the same text and the same
   * rule as `RunRequest.table`, so the survey and a run of the same drop always agree. */
  table?: string;
}

/** Which detected flat, if any, each triangle of a body dropped on the view belongs to -
 * asked once per drop, on demand, the same as a survey and never on every frame. */
export interface DetectRequest {
  id: number;
  type: "detect";
  /** The body, as a base64 binary STL - the same text a run and a survey are handed. */
  stl: string;
  /** The `[reference]` table this body is placed by, as JSON - `SurveyRequest.table`'s own
   * rule, so a detected face's numbers agree with the survey's and a run's. */
  table?: string;
}

export interface BootRequest {
  type: "boot";
  base: string;
  /** How long the runtime may take to come up, in milliseconds. */
  timeout?: number;
}

export type Request = RunRequest | SurveyRequest | DetectRequest | BootRequest;

const BOOT_TIMEOUT = 60_000;
/** How long `loadPyodide` may take before the boot is called a failure, in milliseconds. */

/** What Python's telemetry is handed: two plain functions, attributes as JSON text, times in
 * milliseconds since the epoch - nothing either side has to know the other's objects for. */
const python = {
  span(name: string, start: number, duration: number, attributes: string): void {
    spanned({ name, start, duration, attributes: JSON.parse(attributes) as Attributes });
  },
  log(level: string, logger: string, message: string, time: number, attributes: string): void {
    logged({
      time,
      level: isLevel(level) ? level : "info",
      logger,
      message,
      attributes: JSON.parse(attributes) as Attributes,
    });
  },
};

/** The Python entry point: `bench.worker.start`, with Pyodide's `JsException` - the exception a
 * refused call to the modeller raises - handed in from here, at the edge, so nothing under
 * `bench` has to know it runs in Pyodide. Everything else a run needs - routing `bench`'s logs
 * and spans to `python` above, the kernel, the scene on the wire - is `bench/worker.py`, where
 * it is linted, type-checked and tested like the rest of the package. */
const ENTRY = `
from pyodide.ffi import JsException

import bench.worker

lambda telemetry: bench.worker.start(telemetry, JsException)
`;

/** The survey of a dropped body, as the report a person reads - placed by the project's
 * `[reference]` table exactly as a run's own `reference` is, so the report and a run never
 * disagree about where the mesh sits. `bench.worker.surveyed` is where that placement is
 * done, tested and typed; this line only reaches it, the same way `ENTRY` reaches `start`. */
const SURVEY = "bench.worker.surveyed";

/** Which flat each triangle of a dropped body belongs to, as JSON - placed the same way a
 * survey is, so a detected face and the survey's own numbers never disagree.
 * `bench.worker.detected` is where that placement and the detection are done, tested and
 * typed; this line only reaches it, the same way `SURVEY` reaches `surveyed`. */
const DETECT = "bench.worker.detected";

/** A Python object held from JavaScript, which Python cannot free until it is let go of. */
interface PyProxy {
  destroy(): void;
}

/** `scene_wire`'s answer: the JSON text, and the list of buffers the meshes were taken out
 * into. */
interface PyAnswer extends PyProxy {
  get(index: number): unknown;
}

interface PyList extends PyProxy {
  readonly length: number;
  get(index: number): PyBuffer;
}

/** An `array.array`, readable as a view straight onto Python's memory. */
interface PyBuffer extends PyProxy {
  getBuffer(): { readonly data: Float32Array | Uint32Array; release(): void };
}

/** Every buffer in `list` copied out of Python's memory into one of JavaScript's own - which
 * is what lets the page be handed it as a transfer rather than another copy. */
function copied(list: PyList): (Float32Array | Uint32Array)[] {
  const out: (Float32Array | Uint32Array)[] = [];
  try {
    for (let at = 0; at < list.length; at += 1) {
      const item = list.get(at);
      try {
        const view = item.getBuffer();
        try {
          out.push(view.data.slice());
        } finally {
          view.release();
        }
      } finally {
        item.destroy();
      }
    }
  } finally {
    list.destroy();
  }
  return out;
}

/** The Python entry point, seen from here. The modeller is *optional*, not nullable, and the
 * difference matters: Pyodide hands JavaScript's `null` to Python as its own `JsNull`
 * sentinel, which is not `None` and would sail straight past `if modeller is None` into a
 * kernel wrapped round nothing. `undefined` - which is what leaving the argument off gives
 * - is the one that arrives as `None`. */
type Runner = (
  source: string,
  overrides: string,
  modeller?: Modeller,
  stl?: string,
  table?: string,
  modules?: string,
) => PyAnswer;

/** `SURVEY`, seen from here: a base64 STL and, when there is one, its `[reference]` table as
 * JSON, in - the report's text out. */
type Surveyor = (stl: string, table?: string) => string;

/** `DETECT`, seen from here: the same in, the detected faces as JSON out. */
type Detector = (stl: string, table?: string) => string;

/** What a boot gives back: the three things Python answers. */
interface Entry {
  readonly run: Runner;
  readonly survey: Surveyor;
  readonly detect: Detector;
}

let base: string | null = null;
let bootTimeout = BOOT_TIMEOUT;
let booting: Promise<Entry> | null = null;
let queued: RunRequest | null = null;
/** The survey waiting its turn. A slot of its own, because a run arriving must supersede the
 * run before it and not the survey beside it; and one slot, because a second drop replaces
 * the first body and the report of the first is not wanted any more. */
let surveying: SurveyRequest | null = null;
/** The detection waiting its turn - one slot, for the reason `surveying` is one: a second
 * drop replaces the first body and the first's own detected faces are not wanted any more. */
let detecting: DetectRequest | null = null;
let busy = false;
/** The modeller this worker builds bodies with, or `null` if it would not load. */
let modeller: Modeller | null = null;

const status = (text: string): void => scope.postMessage({ type: "status", text });

function mkdirp(fs: PyodideFS, dir: string): void {
  let walked = "";
  for (const segment of dir.split("/")) {
    if (segment === "") continue;
    walked += `/${segment}`;
    try {
      fs.mkdir(walked);
    } catch {
      // already there, which is the common case
    }
  }
}

/** Reject after `ms`, so a runtime that neither loads nor fails cannot hang the tab.
 *
 * Raises nothing itself: the returned promise rejects, and the caller races it.
 */
function expire(ms: number): { promise: Promise<never>; cancel: () => void } {
  let timer = 0;
  const promise = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`Python did not start in ${Math.round(ms / 1000)} s`)),
      ms,
    ) as unknown as number;
  });
  return { promise, cancel: () => clearTimeout(timer) };
}

/** The solid modeller, or `null` with a line on the status bar saying so.
 *
 * Half a megabyte and about twenty milliseconds, against Python's thirteen megabytes - so it
 * is loaded first, and the wait a person actually sees is still Python's. A failure here is
 * not a failure of the app: flat parts need no modeller, and a printed one comes back fully
 * named with no triangles rather than not at all.
 */
async function solidModeller(at: string): Promise<Modeller | null> {
  try {
    status("loading the solid modeller…");
    return bind(await timedAsync("bench.boot.modeller", () => loadManifold(at)));
  } catch (problem) {
    log("warn", "bench.worker", "the solid modeller did not load", { "error.message": String(problem) });
    status("no solid modeller: flat parts only");
    return null;
  }
}

async function load(): Promise<Entry> {
  if (base === null) throw new Error("the worker was never told where the runtime lives");
  const root = base;
  modeller = await solidModeller(new URL("../manifold/", root).href);
  // One line for the whole of the heavy part: `loadPyodide` fetches the wasm and the
  // standard library and compiles the one and unpacks the other, which is what the wait is
  // actually made of, so the page says so for as long as that lasts rather than flashing
  // three words nobody can read. It does not say "downloading": after the first visit the
  // browser has the files and the wait is the compile, and nothing here can tell which it is
  // before asking.
  status("loading Python runtime (~13 MB the first time)…");
  const pyodide = await timedAsync("bench.boot.python", async () => {
    const module: { loadPyodide: LoadPyodide } = await import(
      /* @vite-ignore */ new URL("pyodide.mjs", root).href
    );
    return module.loadPyodide({
      indexURL: root,
      // Neither stream is the script's: `bench.script.run` redirects both around the exec and
      // hands them back on the scene, where the app can show them. What is left for these two
      // is whatever Python says outside a run - an import, the runtime itself - which belongs
      // in the logs and nowhere a maker has to read.
      stdout: (text: string) => log("debug", "bench.python.stdout", text),
      stderr: (text: string) => log("warn", "bench.python.stderr", text),
    });
  });
  status("starting Python, loading bench…");
  const entry = timed("bench.boot.bench", () => {
    for (const [path, text] of Object.entries(PY_SOURCES)) {
      const full = `/lib/${path}`;
      mkdirp(pyodide.FS, full.slice(0, full.lastIndexOf("/")));
      pyodide.FS.writeFile(full, text, { encoding: "utf8" });
    }
    pyodide.runPython(`import sys\nsys.path.insert(0, "/lib")\nimport bench.script`);
    const start = pyodide.runPython(ENTRY) as (telemetry: typeof python) => Runner;
    return {
      run: start(python),
      survey: pyodide.runPython(SURVEY) as Surveyor,
      detect: pyodide.runPython(DETECT) as Detector,
    };
  });
  log("info", "bench.worker", "ready", { "bench.modeller": modeller !== null });
  status("ready");
  return entry;
}

/** The one boot, started on demand and forgotten again if it fails. */
function boot(): Promise<Entry> {
  if (booting !== null) return booting;
  const clock = expire(bootTimeout);
  const started = Promise.race([load(), clock.promise]);
  booting = started.then(
    (entry) => {
      clock.cancel();
      return entry;
    },
    (problem: unknown) => {
      clock.cancel();
      log("error", "bench.worker", "the runtime did not start", { "error.message": String(problem) });
      // Not memoised: a boot that failed is not an answer, it is a thing to try again.
      booting = null;
      throw problem;
    },
  );
  return booting;
}

/** One run, answered as the scene on the wire. */
function ran(entry: Entry, job: RunRequest): void {
  const attributes = { "bench.run.id": job.id };
  const answer = timed(
    "bench.worker.run",
    () =>
      entry.run(
        job.source,
        JSON.stringify(job.overrides),
        modeller ?? undefined,
        job.stl,
        job.table,
        job.modules,
      ),
    attributes,
  );
  try {
    const scene: unknown = timed("bench.worker.parse", () => JSON.parse(String(answer.get(0))), attributes);
    const buffers = timed("bench.worker.copy", () => copied(answer.get(1) as PyList), attributes);
    // Transferred, not copied again: the page takes the buffers these views were made on.
    scope.postMessage({ id: job.id, scene, buffers }, buffers.map((one) => one.buffer));
  } finally {
    answer.destroy();
  }
}

/** One survey, answered as the report's text. */
function surveyed(entry: Entry, job: SurveyRequest): void {
  const report = timed("bench.worker.survey", () => entry.survey(job.stl, job.table), {
    "bench.run.id": job.id,
  });
  scope.postMessage({ id: job.id, type: "survey", report });
}

/** One detection, answered as the detected faces' JSON. */
function detected(entry: Entry, job: DetectRequest): void {
  const result = timed("bench.worker.detect", () => entry.detect(job.stl, job.table), {
    "bench.run.id": job.id,
  });
  scope.postMessage({ id: job.id, type: "detect", result });
}

function pump(): void {
  if (busy) return;
  // The run first: it is what the keystroke asked for, and the view should follow the
  // typing. The survey goes next, when the typing pauses, which is when there is time to
  // read it; detection last, since it is asked for by a toggle a maker reaches for after
  // that, never by the drop itself.
  const job = queued ?? surveying ?? detecting;
  if (job === null) return;
  if (job.type === "run") queued = null;
  else if (job.type === "survey") surveying = null;
  else detecting = null;
  busy = true;
  void (async () => {
    try {
      const entry = await boot();
      if (job.type === "run") ran(entry, job);
      else if (job.type === "survey") surveyed(entry, job);
      else detected(entry, job);
    } catch (problem) {
      const what =
        job.type === "run"
          ? "a run failed outside the script"
          : job.type === "survey"
            ? "a survey failed"
            : "a detection failed";
      log("error", "bench.worker", what, { "error.message": String(problem) });
      scope.postMessage({ id: job.id, type: job.type, failure: String(problem) });
    } finally {
      busy = false;
      // A macrotask, so every message already queued has folded into `queued` first.
      setTimeout(pump, 0);
    }
  })();
}

scope.addEventListener("message", (event: MessageEvent) => {
  const request = event.data as Request;
  if (request.type === "boot") {
    base = request.base;
    if (request.timeout !== undefined) bootTimeout = request.timeout;
    // The run that awaits this is what reports a failure; this handler only keeps a boot
    // that fails before any run arrives from surfacing as an unhandled rejection.
    boot().catch(() => {});
    return;
  }
  if (request.type === "survey") surveying = request;
  else if (request.type === "detect") detecting = request;
  else queued = request;
  setTimeout(pump, 0);
});
