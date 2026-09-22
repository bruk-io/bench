import { afterEach, describe, expect, it } from "vitest";

import {
  type ConsoleLike,
  type LogRecord,
  type SpanRecord,
  attach,
  consoleSink,
  log,
  now,
  spanned,
  timed,
  timedAsync,
  userTimingSink,
} from "./telemetry";

const detached: (() => void)[] = [];

/** A sink that keeps what it is given, attached until the test ends. */
function kept(): { logs: LogRecord[]; spans: SpanRecord[] } {
  const found = { logs: [] as LogRecord[], spans: [] as SpanRecord[] };
  detached.push(
    attach({
      log: (record) => found.logs.push(record),
      span: (record) => found.spans.push(record),
    }),
  );
  return found;
}

afterEach(() => {
  for (const stop of detached.splice(0)) stop();
  performance.clearMeasures();
});

describe("telemetry, spans", () => {
  it("records a block that returns, with its attributes", () => {
    const found = kept();
    expect(timed("bench.work", () => 7, { "bench.part.ref": "lid" })).toBe(7);
    expect(found.spans).toHaveLength(1);
    expect(found.spans[0]?.name).toBe("bench.work");
    expect(found.spans[0]?.attributes).toEqual({ "bench.part.ref": "lid" });
    expect(found.spans[0]?.duration).toBeGreaterThanOrEqual(0);
  });

  it("records a block that throws with its error type, and still throws", () => {
    const found = kept();
    expect(() =>
      timed("bench.work", () => {
        throw new RangeError("no");
      }),
    ).toThrow(RangeError);
    expect(found.spans[0]?.attributes).toEqual({ "error.type": "RangeError" });
  });

  it("records work that finishes later", async () => {
    const found = kept();
    await timedAsync("bench.later", () => Promise.resolve(1));
    expect(found.spans.map((one) => one.name)).toEqual(["bench.later"]);
  });

  it("times in milliseconds since the epoch, so two threads' spans share a timeline", () => {
    expect(Math.abs(now() - Date.now())).toBeLessThan(1000);
  });

  it("stops sending to a sink once it is detached", () => {
    const found = { spans: [] as SpanRecord[] };
    const stop = attach({ span: (record) => found.spans.push(record) });
    stop();
    timed("bench.work", () => 0);
    expect(found.spans).toEqual([]);
  });

  it("carries on past a sink that throws", () => {
    detached.push(
      attach({
        span: () => {
          throw new Error("broken sink");
        },
      }),
    );
    const found = kept();
    timed("bench.work", () => 0);
    expect(found.spans).toHaveLength(1);
  });
});

describe("telemetry, sinks", () => {
  it("puts a span on the User Timing timeline with its attributes as detail", () => {
    detached.push(attach(userTimingSink));
    spanned({ name: "bench.measured", start: now() - 5, duration: 5, attributes: { "bench.x": 1 } });
    const [entry] = performance.getEntriesByName("bench.measured", "measure") as PerformanceMeasure[];
    expect(entry?.duration).toBeCloseTo(5, 3);
    expect(entry?.detail).toEqual({ "bench.x": 1 });
  });

  it("writes log records at its level and above, with their fields", () => {
    const written: [string, unknown[]][] = [];
    const out: ConsoleLike = {
      debug: (...args: unknown[]) => written.push(["debug", args]),
      info: (...args: unknown[]) => written.push(["info", args]),
      warn: (...args: unknown[]) => written.push(["warn", args]),
      error: (...args: unknown[]) => written.push(["error", args]),
    };
    detached.push(attach(consoleSink("info", out)));
    log("debug", "bench.test", "too quiet");
    log("warn", "bench.test", "heard", { "bench.part.ref": "lid" });
    expect(written).toEqual([["warn", ["[bench.test] heard", { "bench.part.ref": "lid" }]]]);
  });
});
