/** The main thread's side of the worker: one run at a time, latest request wins.
 *
 * Three things live here that the worker cannot do for itself. A **watchdog**, because a
 * script is arbitrary Python and `while True: pass` cannot be interrupted from outside the
 * loop - only `terminate()` ends it, so the bridge holds a timer, kills the worker when it
 * expires and puts a fresh one in its place. **Crash listeners**, because a worker that
 * throws on load, or is handed a message it cannot deserialise, reports that on the worker
 * object and nowhere else. And **validation**, because everything arriving over the wire is
 * unchecked JSON: a payload that is not a scene becomes a failure, never a half-draw.
 *
 * It is also where the worker's telemetry comes home: every log record and span the worker
 * and its Python post is handed to this page's sinks, and the whole round trip of a run -
 * from asking to the scene arriving - is a span of its own, `bench.run`.
 */
import { type Scene, received } from "./scene";
import { type Attributes, type LogRecord, type SpanRecord, isLevel, log, logged, now, spanned } from "./telemetry";
import type { Request } from "./worker";
import BenchWorker from "./worker?worker";

export interface BridgeHandlers {
  onStatus(text: string): void;
  onScene(scene: Scene): void;
  onFailure(message: string): void;
  /** The watchdog fired: this source is a runaway, not merely a failure. */
  onRunaway(message: string): void;
  /** A run started, or stopped for any reason; the Stop button follows this. */
  onBusy(busy: boolean): void;
  /** The survey asked for last came back - as the report, or as why there is none. */
  onSurvey(outcome: SurveyOutcome): void;
  /** The detection asked for last came back - as the detected faces' JSON, or as why there
   * is none. */
  onDetect(outcome: DetectOutcome): void;
}

/** What a survey ends in: the report's text, or the reason there is none - the reader
 * refusing the file, or the worker being replaced under it. */
export type SurveyOutcome = { readonly report: string } | { readonly problem: string };

/** What a detection ends in: the detected faces as JSON text, or the reason there is none -
 * the same two as a survey's. */
export type DetectOutcome = { readonly result: string } | { readonly problem: string };

export interface BridgeOptions {
  /** How long one run may take before the worker is killed, in milliseconds. */
  watchdog?: number;
  /** How long the runtime may take to come up, in milliseconds. */
  bootTimeout?: number;
}

export interface Bridge {
  /** Ask for a run of `source`; supersedes any request not yet started.
   *
   * `stl` is a body to hand the script as `reference`, base64 encoded. Left off when there
   * is nothing to hand it. `table` is the open project's `[reference]` table, as JSON - left
   * off unless `stl` is the very body that table's own `file` names, so the mesh is placed
   * before the script sees it. `modules` is the open project's other scripts, as JSON
   * (`{name: text}`) - left off for a project of one script, which is most of them - so
   * `source` can import them (task-50). */
  request(
    source: string,
    overrides: Record<string, unknown>,
    stl?: string,
    table?: string,
    modules?: string,
  ): void;
  /** Ask for the survey of `stl`, a body as base64; supersedes any survey not yet answered.
   *
   * Not a run: it is outside the watchdog, because a survey is bounded by the triangles it
   * was handed and cannot loop, and outside `onBusy`, because the Stop button is for the
   * script. The worker takes it after any run waiting ahead of it. `table` is `request`'s
   * own, so the survey and a run of the same drop are placed alike. */
  survey(stl: string, table?: string): void;
  /** Ask which flat, by index, each triangle of `stl` belongs to; supersedes any detection
   * not yet answered. `survey`'s own rules: outside the watchdog and `onBusy`, taken after
   * any run and any survey ahead of it, `table` placing it the same way. */
  detect(stl: string, table?: string): void;
  /** Kill whatever is running and put a fresh worker in its place. */
  stop(reason?: string): void;
  /** Whether a run is in flight. */
  running(): boolean;
}

const WATCHDOG = 15_000;
/** How long a run may take before it is called a runaway, in milliseconds. */

const LOGGER = "bench.bridge";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const isAttributes = (value: unknown): value is Attributes =>
  isRecord(value) &&
  Object.values(value).every((one) => ["string", "number", "boolean"].includes(typeof one));

/** A log record the worker posted, or `null` for anything that is not one. */
function logRecord(value: unknown): LogRecord | null {
  if (!isRecord(value) || !isLevel(value["level"]) || !isAttributes(value["attributes"])) return null;
  const { time, logger, message } = value;
  if (typeof time !== "number" || typeof logger !== "string" || typeof message !== "string") return null;
  return { time, level: value["level"], logger, message, attributes: value["attributes"] };
}

/** A span the worker posted, or `null` for anything that is not one. */
function spanRecord(value: unknown): SpanRecord | null {
  if (!isRecord(value) || !isAttributes(value["attributes"])) return null;
  const { name, start, duration } = value;
  if (typeof name !== "string" || typeof start !== "number" || typeof duration !== "number") return null;
  return { name, start, duration, attributes: value["attributes"] };
}

export function connect(handlers: BridgeHandlers, options: BridgeOptions = {}): Bridge {
  const limit = options.watchdog ?? WATCHDOG;
  const seconds = Math.round(limit / 1000);
  let worker: Worker = spawn();
  let next = 1;
  let latest = 0;
  let asked = 0;
  let timer: number | undefined;
  let busy = false;
  let ready = false;
  /** The id of the survey still to be answered, or 0 for none. */
  let surveyed = 0;
  /** The id of the detection still to be answered, or 0 for none. */
  let detected = 0;

  function settle(): void {
    window.clearTimeout(timer);
    timer = undefined;
    if (!busy) return;
    busy = false;
    handlers.onBusy(false);
  }

  /** The run that just ended, as one span from asking to answering - not `bench.run`, which
   * is Python's own run inside the worker and one stretch of this. */
  function ended(outcome: string): void {
    spanned({
      name: "bench.run.roundtrip",
      start: asked,
      duration: now() - asked,
      attributes: { "bench.run.id": latest, "bench.run.outcome": outcome },
    });
  }

  /** Start the watchdog for the run in flight.
   *
   * Only the script is timed. The first run usually waits on the runtime coming up, which
   * is a download of tens of megabytes and legitimately slower than any script; that wait
   * has its own timeout inside the worker, so the clock here starts at "ready".
   */
  function arm(): void {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      settle();
      replace();
      ended("runaway");
      log("warn", LOGGER, "a run passed the watchdog and its worker was replaced", {
        "bench.watchdog.ms": limit,
      });
      handlers.onRunaway(`the script did not finish in ${seconds} s and was stopped`);
    }, limit);
  }

  function answered(data: unknown): void {
    if (typeof data !== "object" || data === null) {
      log("error", LOGGER, "the worker sent something that is not a message");
      handlers.onFailure(`unexpected message from the worker: ${String(data)}`);
      return;
    }
    const message = data as Record<string, unknown>;
    if (message["type"] === "telemetry") {
      const record = logRecord(message["log"]);
      if (record !== null) logged(record);
      const span = spanRecord(message["span"]);
      if (span !== null) spanned(span);
      return;
    }
    if (message["type"] === "status") {
      const text = String(message["text"]);
      if (text === "ready") {
        ready = true;
        if (busy) arm();
      }
      handlers.onStatus(text);
      return;
    }
    if (message["type"] === "survey") {
      if (message["id"] !== surveyed) return; // a superseded survey, or one a stop left behind
      surveyed = 0;
      const report = message["report"];
      handlers.onSurvey(
        typeof report === "string" ? { report } : { problem: String(message["failure"]) },
      );
      return;
    }
    if (message["type"] === "detect") {
      if (message["id"] !== detected) return; // a superseded detection, or one a stop left behind
      detected = 0;
      const result = message["result"];
      handlers.onDetect(
        typeof result === "string" ? { result } : { problem: String(message["failure"]) },
      );
      return;
    }
    if (message["id"] !== latest) return; // a superseded run, or one a stop left behind
    settle();
    if (typeof message["failure"] === "string") {
      ended("failure");
      handlers.onFailure(message["failure"]);
      return;
    }
    const found = received(message["scene"], message["buffers"]);
    if ("problem" in found) {
      ended("malformed");
      log("error", LOGGER, "the worker sent a scene of the wrong shape", { "error.message": found.problem });
      handlers.onFailure(`unexpected scene shape: ${found.problem}`);
      return;
    }
    ended(found.scene.ok ? "ok" : "error");
    handlers.onScene(found.scene);
  }

  function spawn(): Worker {
    const fresh = new BenchWorker();
    fresh.addEventListener("message", (event: MessageEvent) => {
      answered(event.data);
    });
    // A worker that fails to load its own module, or is handed something it cannot
    // deserialise, says so here and nowhere else.
    fresh.addEventListener("error", (event: ErrorEvent) => {
      settle();
      log("error", LOGGER, "the worker crashed", { "error.message": event.message || "no reason given" });
      handlers.onFailure(`the Python worker crashed: ${event.message || "no reason given"}`);
    });
    fresh.addEventListener("messageerror", () => {
      settle();
      log("error", LOGGER, "the worker sent a message the page could not read");
      handlers.onFailure("the Python worker sent a message the page could not read");
    });
    // The worker resolves the runtime against its own bundled URL, which sits in the
    // assets folder; the page knows where the app's base really is.
    const base = new URL(`${import.meta.env.BASE_URL}pyodide/`, location.href).href;
    const boot: Request = { type: "boot", base };
    if (options.bootTimeout !== undefined) boot.timeout = options.bootTimeout;
    fresh.postMessage(boot);
    return fresh;
  }

  function replace(): void {
    worker.terminate();
    ready = false;
    // Nothing the dead worker said is wanted any more, and a fresh one starts its ids
    // from scratch; bumping `latest` past every id in flight is what drops the leftovers.
    latest = next++;
    worker = spawn();
    // A survey the dead worker was going to answer is not coming; say so rather than leave
    // the page waiting on it.
    if (surveyed !== 0) {
      surveyed = 0;
      handlers.onSurvey({ problem: "the worker was replaced before the survey finished" });
    }
    if (detected !== 0) {
      detected = 0;
      handlers.onDetect({ problem: "the worker was replaced before the detection finished" });
    }
  }

  function stop(reason?: string): void {
    if (busy) ended("stopped");
    settle();
    replace();
    if (reason !== undefined) handlers.onFailure(reason);
  }

  return {
    request(source, overrides, stl, table, modules) {
      latest = next++;
      asked = now();
      window.clearTimeout(timer);
      timer = undefined;
      if (ready) arm();
      if (!busy) {
        busy = true;
        handlers.onBusy(true);
      }
      worker.postMessage({
        id: latest,
        type: "run",
        source,
        overrides,
        // Spread rather than `stl`/`table`/`modules`, because `exactOptionalPropertyTypes`
        // is on and means it: a run with nothing dropped, nothing to place it with, or no
        // sibling module leaves the property off rather than setting it undefined.
        ...(stl === undefined ? {} : { stl }),
        ...(table === undefined ? {} : { table }),
        ...(modules === undefined ? {} : { modules }),
      } satisfies Request);
    },
    survey(stl, table) {
      surveyed = next++;
      worker.postMessage({
        id: surveyed,
        type: "survey",
        stl,
        ...(table === undefined ? {} : { table }),
      } satisfies Request);
    },
    detect(stl, table) {
      detected = next++;
      worker.postMessage({
        id: detected,
        type: "detect",
        stl,
        ...(table === undefined ? {} : { table }),
      } satisfies Request);
    },
    stop,
    running: () => busy,
  };
}
