/** Telemetry: the app's log records and timed spans, and the one place a collector plugs in.
 *
 * Everything the app says about itself - the page, the worker, and the Python running in the
 * worker - arrives here as a `LogRecord` or a `SpanRecord` and goes to every attached `Sink`.
 * Two sinks ship: `consoleSink`, levelled, for a person with DevTools open, and
 * `userTimingSink`, which puts every span on this page's User Timing timeline as a
 * `performance.measure` - where the Performance panel draws it and where a RUM agent or
 * OpenTelemetry's web instrumentation already looks. Attaching Datadog, Grafana Faro or an
 * OTLP exporter is one more `attach` in `main.ts`; nothing else in the app changes.
 *
 * Names follow OpenTelemetry's conventions: spans are lowercase and dotted, `bench.` first,
 * with attributes such as `bench.part.ref`, and `error.type` on a span whose work threw.
 * Times are milliseconds since the epoch, so a span timed in the worker lands in the right
 * place on the page's timeline whatever the two threads' own time origins are.
 */

export type Attribute = string | number | boolean;
export type Attributes = Readonly<Record<string, Attribute>>;
export type Level = "debug" | "info" | "warn" | "error";

export interface LogRecord {
  readonly time: number;
  readonly level: Level;
  readonly logger: string;
  readonly message: string;
  readonly attributes: Attributes;
}

export interface SpanRecord {
  readonly name: string;
  readonly start: number;
  readonly duration: number;
  readonly attributes: Attributes;
}

/** Somewhere records go. Either half may be left out. */
export interface Sink {
  log?(record: LogRecord): void;
  span?(record: SpanRecord): void;
}

const RANK: Readonly<Record<Level, number>> = { debug: 10, info: 20, warn: 30, error: 40 };

/** Whether `value` names a level. */
export const isLevel = (value: unknown): value is Level =>
  typeof value === "string" && Object.hasOwn(RANK, value);

/** Milliseconds since the epoch, to the precision this thread's clock has. */
export const now = (): number => performance.timeOrigin + performance.now();

const sinks = new Set<Sink>();

/** Send every record from now on to `sink` as well. Returns the way to stop. */
export function attach(sink: Sink): () => void {
  sinks.add(sink);
  return () => {
    sinks.delete(sink);
  };
}

/** Hand one log record to every sink. A sink that throws is its own problem, not the app's. */
export function logged(record: LogRecord): void {
  for (const sink of sinks) {
    try {
      sink.log?.(record);
    } catch {
      // a broken sink must not take the thing it was watching down with it
    }
  }
}

/** Hand one finished span to every sink. */
export function spanned(record: SpanRecord): void {
  for (const sink of sinks) {
    try {
      sink.span?.(record);
    } catch {
      // as above
    }
  }
}

/** A log record stamped now. */
export function log(level: Level, logger: string, message: string, attributes: Attributes = {}): void {
  logged({ time: now(), level, logger, message, attributes });
}

/** Run `work` as one span called `name`, recorded whether it returns or throws. */
export function timed<T>(name: string, work: () => T, attributes: Attributes = {}): T {
  const start = now();
  let value: T;
  try {
    value = work();
  } catch (problem) {
    spanned({ name, start, duration: now() - start, attributes: withError(attributes, problem) });
    throw problem;
  }
  spanned({ name, start, duration: now() - start, attributes });
  return value;
}

/** The same for work that finishes later. */
export async function timedAsync<T>(
  name: string,
  work: () => Promise<T>,
  attributes: Attributes = {},
): Promise<T> {
  const start = now();
  try {
    const value = await work();
    spanned({ name, start, duration: now() - start, attributes });
    return value;
  } catch (problem) {
    spanned({ name, start, duration: now() - start, attributes: withError(attributes, problem) });
    throw problem;
  }
}

const withError = (attributes: Attributes, problem: unknown): Attributes => ({
  ...attributes,
  "error.type": problem instanceof Error ? problem.name : typeof problem,
});

/** The parts of `console` a sink writes to. */
export type ConsoleLike = Pick<Console, "debug" | "info" | "warn" | "error">;

/** Log records at `least` and above, to the console, with their fields beside the message. */
export function consoleSink(least: Level = "info", out: ConsoleLike = console): Sink {
  return {
    log(record) {
      if (RANK[record.level] < RANK[least]) return;
      out[record.level](`[${record.logger}] ${record.message}`, record.attributes);
    },
  };
}

/** Every span as a User Timing measure on this thread's timeline, its attributes as the
 * measure's `detail`. */
export const userTimingSink: Sink = {
  span(record) {
    try {
      performance.measure(record.name, {
        start: Math.max(0, record.start - performance.timeOrigin),
        duration: record.duration,
        detail: record.attributes,
      });
    } catch {
      // a timeline that will not take the entry - an old browser - loses the span, not the app
    }
  },
};
