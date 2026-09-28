/** The main thread's side of the worker: one run at a time, latest request wins.
 *
 * Three things live here that the worker cannot do for itself. A **watchdog**, because a
 * script is arbitrary Python and `while True: pass` cannot be interrupted from outside the
 * loop - only `terminate()` ends it, so the bridge holds a timer, kills the worker when it
 * expires and puts a fresh one in its place. The timer runs from the moment the worker says a
 * run has *started* - not from asking - so what the worker was doing first (booting, reading
 * the reference, a run this one superseded, a survey) is never counted as the script's own
 * (task-96); and a run asked for while a survey or a detection is working takes the worker
 * from it rather than waiting, since those are bounded but can take minutes on a large body. **Crash listeners**, because a worker that
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
import type { DetectRequest, Request, RunRequest, SurveyRequest } from "./worker";
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
   * script. The worker takes it after any run waiting ahead of it, and a run asked for while
   * it is working takes the worker from it - it starts again after that run (task-96): a
   * survey of a quarter of a million triangles takes minutes, and a run is what somebody is
   * waiting on. `table` is `request`'s own, so the survey and a run of the same drop are
   * placed alike. */
  survey(stl: string, table?: string): void;
  /** Ask which flat, by index, each triangle of `stl` belongs to; supersedes any detection
   * not yet answered. `survey`'s own rules: outside the watchdog and `onBusy`, taken after
   * any run and any survey ahead of it and set aside for a run, `table` placing it the same
   * way. */
  detect(stl: string, table?: string): void;
  /** Kill whatever is running and put a fresh worker in its place. A survey or detection
   * still to be answered is told the worker went, as a problem. */
  stop(reason?: string): void;
  /** Whether a run is in flight. */
  running(): boolean;
}

const WATCHDOG = 15_000;
/** How long a run may take, from the moment it starts, before it is called a runaway, in
 * milliseconds. */

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
  /** The id of the run the watchdog is timing, or 0 while it times nothing. */
  let timing = 0;
  let busy = false;
  /** The run asked for last, until it is answered - kept, so a worker replaced under it for
   * any reason but this run's own can be handed it again. */
  let wanted: RunRequest | null = null;
  /** The survey still to be answered, or `null` for none - kept for the same reason. */
  let surveyed: SurveyRequest | null = null;
  /** The detection still to be answered, or `null` for none. */
  let detected: DetectRequest | null = null;
  /** What the worker said it is working on, from its `started` to its answer - `null` while
   * it is booting, between jobs, or idle. */
  let working: { readonly id: number; readonly job: Request["type"] } | null = null;

  function settle(): void {
    disarm();
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

  function disarm(): void {
    window.clearTimeout(timer);
    timer = undefined;
    timing = 0;
  }

  /** Start the watchdog for run `id`, which the worker has just said it started.
   *
   * Only the script is timed. Everything before it - the runtime coming up, which is a
   * download of tens of megabytes; the reference being read; a run this one superseded, still
   * finishing; a survey - is not this script's, and each is bounded on its own: the boot by
   * its own timeout inside the worker, a superseded run by the watchdog it had when it
   * started, a survey or detection by the triangles it was handed (and by `request`, which
   * takes the worker from one). So a runaway still dies `limit` after it began.
   */
  function arm(id: number): void {
    window.clearTimeout(timer);
    timing = id;
    timer = window.setTimeout(() => {
      expired(id);
    }, limit);
  }

  function expired(id: number): void {
    timer = undefined;
    timing = 0;
    if (id !== latest && wanted !== null) {
      // A run somebody has already moved on from is the runaway, not the one they asked for
      // since: that one is handed to the fresh worker rather than blamed for the old one.
      log("warn", LOGGER, "a superseded run passed the watchdog; its worker was replaced", {
        "bench.watchdog.ms": limit,
        "bench.run.id": id,
      });
      replace(true);
      return;
    }
    settle();
    replace(false);
    ended("runaway");
    log("warn", LOGGER, "a run passed the watchdog and its worker was replaced", {
      "bench.watchdog.ms": limit,
    });
    handlers.onRunaway(`the script did not finish in ${seconds} s and was stopped`);
  }

  /** The worker has stopped working on job `id`: its answer came back. */
  function done(id: unknown): void {
    if (working?.id === id) working = null;
    if (timing === id) disarm();
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
      handlers.onStatus(String(message["text"]));
      return;
    }
    if (message["type"] === "started") {
      const id = message["id"];
      const job = message["job"];
      if (typeof id !== "number" || (job !== "run" && job !== "survey" && job !== "detect")) return;
      working = { id, job };
      // Every run that starts is timed, a superseded one too: one that never ends would
      // otherwise hold the worker from the run asked for since, for ever.
      if (job === "run") arm(id);
      return;
    }
    done(message["id"]);
    if (message["type"] === "survey") {
      if (message["id"] !== surveyed?.id) return; // a superseded survey, or one a stop left behind
      surveyed = null;
      const report = message["report"];
      handlers.onSurvey(
        typeof report === "string" ? { report } : { problem: String(message["failure"]) },
      );
      return;
    }
    if (message["type"] === "detect") {
      if (message["id"] !== detected?.id) return; // a superseded detection, or one a stop left behind
      detected = null;
      const result = message["result"];
      handlers.onDetect(
        typeof result === "string" ? { result } : { problem: String(message["failure"]) },
      );
      return;
    }
    if (message["id"] !== latest) return; // a superseded run, or one a stop left behind
    wanted = null;
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

  /** Put a fresh worker in the dead one's place. `again` hands it everything still wanted -
   * the run asked for last, the survey and the detection - under the ids they were asked
   * with, for a worker replaced under them for someone else's sake; otherwise nothing the
   * dead worker was asked is wanted any more, and a survey or detection still owed is told
   * so. */
  function replace(again: boolean): void {
    worker.terminate();
    working = null;
    worker = spawn();
    if (again) {
      if (wanted !== null) worker.postMessage(wanted);
      if (surveyed !== null) worker.postMessage(surveyed);
      if (detected !== null) worker.postMessage(detected);
      return;
    }
    // Bumping `latest` past every id in flight is what drops anything the dead worker said
    // on its way out.
    latest = next++;
    wanted = null;
    if (surveyed !== null) {
      surveyed = null;
      handlers.onSurvey({ problem: "the worker was replaced before the survey finished" });
    }
    if (detected !== null) {
      detected = null;
      handlers.onDetect({ problem: "the worker was replaced before the detection finished" });
    }
  }

  function stop(reason?: string): void {
    if (busy) ended("stopped");
    settle();
    replace(false);
    if (reason !== undefined) handlers.onFailure(reason);
  }

  return {
    request(source, overrides, stl, table, modules) {
      latest = next++;
      asked = now();
      if (!busy) {
        busy = true;
        handlers.onBusy(true);
      }
      wanted = {
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
      };
      if (working !== null && working.job !== "run") {
        // A survey or a detection cannot be interrupted either, and one of a large body takes
        // minutes; the person pressing Run is not made to wait it out. It is asked again,
        // after the run, of the fresh worker.
        log("info", LOGGER, `a run took the worker from a ${working.job}, which starts again after it`, {
          "bench.run.id": latest,
        });
        replace(true);
        return;
      }
      worker.postMessage(wanted);
    },
    survey(stl, table) {
      surveyed = {
        id: next++,
        type: "survey",
        stl,
        ...(table === undefined ? {} : { table }),
      };
      worker.postMessage(surveyed);
    },
    detect(stl, table) {
      detected = {
        id: next++,
        type: "detect",
        stl,
        ...(table === undefined ? {} : { table }),
      };
      worker.postMessage(detected);
    },
    stop,
    running: () => busy,
  };
}
