import { describe, expect, it } from "vitest";

import {
  type NamedOrigin,
  type Point3,
  between,
  distances,
  fieldText,
  fieldValue,
  nearest,
  resolvedOrigin,
  resolvedUp,
  shown,
} from "./pick";
import { type ReferenceTable, fromToml, toml } from "./values";

/** `bench.survey.ROUND`, as `bench.worker.detected` reports it - the figure the app is handed,
 * never one this test holds an opinion about. */
const ROUND = 0.01;

/** decision-4's systainer foot, as the detection reports the three points its `origin` words
 * name: a box from (606.795, -116.868, 0) to (651.795, -78.868, 6.8). */
const LOW: Point3 = [606.795, -116.868, 0];
const HIGH: Point3 = [651.795, -78.868, 6.8];
const CENTRE: Point3 = [629.295, -97.868, 3.4];
const ORIGINS: readonly NamedOrigin[] = [
  { name: "low", point: LOW },
  { name: "high", point: HIGH },
  { name: "centre", point: CENTRE },
];

describe("pick, the snap to a named word", () => {
  it("writes the word for a point that is the point that word names", () => {
    expect(resolvedOrigin(LOW, ORIGINS, ROUND)).toBe("low");
    expect(resolvedOrigin(HIGH, ORIGINS, ROUND)).toBe("high");
    expect(resolvedOrigin(CENTRE, ORIGINS, ROUND)).toBe("centre");
  });

  it("writes the word for a point off it by less than the detection's own figure", () => {
    const nearly: Point3 = [LOW[0] + 0.004, LOW[1] - 0.003, LOW[2] + 0.002];
    expect(between(nearly, LOW)).toBeLessThan(ROUND);
    expect(resolvedOrigin(nearly, ORIGINS, ROUND)).toBe("low");
  });

  it("writes the triple it measured for a point twice that figure away", () => {
    const off: Point3 = [LOW[0] + 2 * ROUND, LOW[1], LOW[2]];
    expect(between(off, LOW)).toBeGreaterThan(ROUND);
    expect(resolvedOrigin(off, ORIGINS, ROUND)).toEqual(off);
  });

  it("writes the triple it measured for an ordinary point on a face", () => {
    const somewhere: Point3 = [620.1, -100.25, 6.8];
    expect(resolvedOrigin(somewhere, ORIGINS, ROUND)).toEqual(somewhere);
  });

  it("writes the triple when there are no named points to be near", () => {
    expect(resolvedOrigin(LOW, [], ROUND)).toEqual(LOW);
    expect(nearest(LOW, [])).toBeNull();
  });

  it("reads a picked normal as the triple it measured, never as an axis word", () => {
    // No tolerance on an angle exists to snap this with - decision-7 says so plainly.
    expect(resolvedUp([0, 0, 0.9999999])).toEqual([0, 0, 0.9999999]);
  });
});

describe("pick, the readout", () => {
  it("says how far a point is from each named point, in the order they were given", () => {
    const away = distances([LOW[0], LOW[1], LOW[2] + 6.8], ORIGINS);
    expect(away.map((one) => one.name)).toEqual(["low", "high", "centre"]);
    expect(away[0]?.away).toBeCloseTo(6.8, 9);
    expect(nearest([HIGH[0], HIGH[1], HIGH[2]], ORIGINS)?.name).toBe("high");
  });

  it("rounds for the eye only", () => {
    expect(shown([1.23456, -0.5, 0])).toBe("(1.235, -0.500, 0.000)");
    // The value written down is never the shown one: three decimals is a tenth of `ROUND`,
    // which would be enough to push a point that *is* `low` out of its own snap.
    const noisy: Point3 = [0.1 + 0.2, 0, 0];
    expect(shown(noisy)).toBe("(0.300, 0.000, 0.000)");
    expect(resolvedOrigin(noisy, [{ name: "low", point: noisy }], ROUND)).toBe("low");
  });
});

describe("pick, a field's text", () => {
  it("reads three numbers as a triple and anything else as the word it is", () => {
    expect(fieldValue("1, 2, 3")).toEqual([1, 2, 3]);
    expect(fieldValue(" -0.5,0,1e2 ")).toEqual([-0.5, 0, 100]);
    expect(fieldValue("low")).toBe("low");
    expect(fieldValue("+Z")).toBe("+Z");
  });

  it("reads nothing as nothing, and three of something that is not a number as nothing", () => {
    expect(fieldValue("   ")).toBeNull();
    expect(fieldValue(", ,")).toBeNull();
    expect(fieldValue("low, high, centre")).toBeNull();
  });

  it("writes a value back the way it came in", () => {
    expect(fieldText("low")).toBe("low");
    expect(fieldText([1.5, 0, -2])).toBe("1.5, 0, -2");
    expect(fieldValue(fieldText([606.795, -116.868, 0]))).toEqual([606.795, -116.868, 0]);
  });
});

describe("pick, into a [reference] table", () => {
  it("round-trips a picked placement through the file `values.ts` writes and reads", () => {
    // A hit point as a raycast actually gives one - not a tidy triple, which would hide a
    // formatting mismatch between what is written and what can be read back.
    const hit: Point3 = [606.795 + 0.1 + 0.2, -116.868, 6.8 / 3];
    const table: ReferenceTable = {
      file: "foot.stl",
      origin: resolvedOrigin(hit, ORIGINS, ROUND),
      up: resolvedUp([0, 0, 1]),
      along: fieldValue("+X") ?? "",
    };

    const text = toml({}, "foot.py", [], table);
    const read = fromToml(text);

    expect(read).toEqual({ ok: true, values: {}, reference: table });
    // Full precision, not the readout's three decimals: the file holds what was measured.
    expect(text).toContain(`origin = [${hit.join(", ")}]`);
    expect(text).toContain("origin = [607.095, -116.868, 2.2666666666666666]");
    expect(text).toContain("up = [0, 0, 1]");
    expect(text).toContain('along = "+X"');
  });

  it("round-trips a placement whose origin snapped to a word", () => {
    const table: ReferenceTable = {
      file: "foot.stl",
      origin: resolvedOrigin(LOW, ORIGINS, ROUND),
      up: "+Z",
      along: "+X",
    };
    expect(fromToml(toml({}, "foot.py", [], table)).ok).toBe(true);
    expect(fromToml(toml({}, "foot.py", [], table))).toEqual({
      ok: true,
      values: {},
      reference: { file: "foot.stl", origin: "low", up: "+Z", along: "+X" },
    });
  });
});
