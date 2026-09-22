import { describe, expect, it } from "vitest";

import { type ReferenceTable, fromToml, stemOf, toml, tomlName } from "./values";

const CABINET = "gridfinity_cabinet.py";

describe("values, naming", () => {
  it("names the values file for its script", () => {
    expect(tomlName(CABINET)).toBe("gridfinity_cabinet.toml");
    expect(stemOf(CABINET)).toBe("gridfinity_cabinet");
    expect(stemOf("cabinet")).toBe("cabinet");
  });
});

describe("values, writing", () => {
  it("writes one [values] table, naming the script", () => {
    const text = toml({ units_x: 6, kerf: 0.25, baseplate: false, labels: "bits, taps" }, CABINET);
    expect(text).toBe(
      "# The values gridfinity_cabinet.py builds with. A field left out keeps the script's own default.\n" +
        "[values]\n" +
        "units_x = 6\n" +
        "kerf = 0.25\n" +
        "baseplate = false\n" +
        'labels = "bits, taps"\n',
    );
  });

  it("writes an empty table for a project with no values, which is still a file", () => {
    expect(toml({}, "plate.py")).toContain("[values]\n");
    expect(fromToml(toml({}, "plate.py"))).toEqual({ ok: true, values: {}, reference: null });
  });

  it("writes the values in the script's order when it knows it", () => {
    const text = toml({ kerf: 0.25, units_x: 6, extra: 1 }, CABINET, ["units_x", "units_y", "kerf"]);
    expect(text.split("\n").slice(2, 5)).toEqual(["units_x = 6", "kerf = 0.25", "extra = 1"]);
  });

  it("escapes what a basic string cannot hold, and quotes a key that is not bare", () => {
    const text = toml({ "odd key": 'say "hi"\\\n\ttab' }, "x.py");
    expect(text).toContain('"odd key" = "say \\"hi\\"\\\\\\n\\ttab\\u0001"');
    expect(fromToml(text)).toEqual({
      ok: true,
      values: { "odd key": 'say "hi"\\\n\ttab' },
      reference: null,
    });
  });

  it("writes the [reference] table beside [values], file/origin/up/along in that order", () => {
    const reference: ReferenceTable = { along: "+X", file: "obj_2.stl", up: "+Z", origin: "low" };
    const text = toml({ draft: 8.4 }, "systainer_foot.py", [], reference);
    expect(text).toBe(
      "# The values systainer_foot.py builds with. A field left out keeps the script's own default.\n" +
        "[values]\n" +
        "draft = 8.4\n" +
        "\n" +
        "[reference]\n" +
        'file = "obj_2.stl"\n' +
        'origin = "low"\n' +
        'up = "+Z"\n' +
        'along = "+X"\n',
    );
  });

  it("writes a triple as [x, y, z]", () => {
    const reference: ReferenceTable = {
      file: "obj_2.stl",
      origin: [606.795, -116.868, 0.0],
      up: "+Z",
      along: "+X",
    };
    const text = toml({}, "foot.py", [], reference);
    expect(text).toContain("origin = [606.795, -116.868, 0]\n");
  });

  it("writes no [reference] table for a project with none", () => {
    expect(toml({}, "plate.py", [], null)).not.toContain("[reference]");
  });
});

describe("values, reading", () => {
  it("reads back what it wrote", () => {
    const table = { units_x: 6, kerf: 0.25, baseplate: true, labels: "bits, taps", none: "" };
    expect(fromToml(toml(table, CABINET))).toEqual({ ok: true, values: table, reference: null });
  });

  it("reads the file tools/build.py reads, comments and all", () => {
    const text = [
      "# a comment",
      "",
      "[values]",
      "units_x = 4   # across",
      "units_y=2",
      "kerf = 0.25",
      "big = 1_000",
      "small = -2.5e-3",
      "baseplate = true",
      "labels = 'bits, taps'",
      '"quoted key" = "x"',
    ].join("\n");
    expect(fromToml(text)).toEqual({
      ok: true,
      values: {
        units_x: 4,
        units_y: 2,
        kerf: 0.25,
        big: 1000,
        small: -0.0025,
        baseplate: true,
        labels: "bits, taps",
        "quoted key": "x",
      },
      reference: null,
    });
  });

  it("passes over every other table unread, so a file that grew one still opens", () => {
    const text = [
      "title = 'root'",
      "[[measured]]",
      'name = "wall"',
      'between = ["plane-3", "plane-7"]',
      "value = 2.41",
      "[values]",
      "w = 3",
      "[other]",
      "w = 9",
    ].join("\n");
    expect(fromToml(text)).toEqual({ ok: true, values: { w: 3 }, reference: null });
  });

  it("is empty for a document with no values table, and has no reference for one with none", () => {
    expect(fromToml("")).toEqual({ ok: true, values: {}, reference: null });
    expect(fromToml("# nothing\n[measured]\nx = 1\n")).toEqual({
      ok: true,
      values: {},
      reference: null,
    });
  });

  it("names the line it cannot read", () => {
    const bad = (lines: string[]): string => {
      const found = fromToml(["[values]", ...lines].join("\n"));
      return found.ok ? "" : found.problem;
    };
    expect(bad(["w = [1, 2]"])).toBe("line 2: w is not a number, a string or true/false");
    expect(bad(["w = 3,"])).toBe("line 2: w is not a number, a string or true/false");
    expect(bad(["w = inf"])).toBe("line 2: w is not a number, a string or true/false");
    expect(bad(['w = """multi"""'])).toBe("line 2: w is not a number, a string or true/false");
    expect(bad(["w 3"])).toBe('line 2 has no "=" after w');
    expect(bad(["= 3"])).toBe("line 2 is not a key and a value");
    expect(bad(["w = 1", "w = 2"])).toBe("line 3 sets w a second time");
  });
});

describe("values, [reference]", () => {
  it("reads decision-4's own worked example - words for origin, up and along", () => {
    const text = [
      "[reference]",
      'file = "obj_2.stl"',
      'origin = "low"',
      'up = "+Z"',
      'along = "+X"',
    ].join("\n");
    expect(fromToml(text)).toEqual({
      ok: true,
      values: {},
      reference: { file: "obj_2.stl", origin: "low", up: "+Z", along: "+X" },
    });
  });

  it("reads a triple of numbers for origin, up or along alike", () => {
    const text = [
      "[reference]",
      'file = "obj_2.stl"',
      "origin = [606.795, -116.868, 0.0]",
      "up = [0, 0, 1]",
      "along = [1, 0, 0]",
    ].join("\n");
    expect(fromToml(text)).toEqual({
      ok: true,
      values: {},
      reference: {
        file: "obj_2.stl",
        origin: [606.795, -116.868, 0.0],
        up: [0, 0, 1],
        along: [1, 0, 0],
      },
    });
  });

  it("reads a triple with whitespace and a trailing comma", () => {
    const text = ["[reference]", "origin = [ 1.5 , -2 ,  3.25 , ]"].join("\n");
    expect(fromToml(text)).toEqual({
      ok: true,
      values: {},
      reference: { origin: [1.5, -2, 3.25] },
    });
  });

  it("keeps [values] and [reference] apart", () => {
    const text = ["[values]", "units_x = 4", "[reference]", 'file = "a.stl"', 'origin = "low"'].join(
      "\n",
    );
    expect(fromToml(text)).toEqual({
      ok: true,
      values: { units_x: 4 },
      reference: { file: "a.stl", origin: "low" },
    });
  });

  it("is null for a document with no [reference] table, and an empty table for one with no keys", () => {
    expect(fromToml("[values]\nw = 1\n")).toEqual({ ok: true, values: { w: 1 }, reference: null });
    expect(fromToml("[reference]\n")).toEqual({ ok: true, values: {}, reference: {} });
  });

  it("round-trips what it wrote, words and triples alike", () => {
    const reference: ReferenceTable = {
      file: "obj_2.stl",
      origin: [606.795, -116.868, 0.0],
      up: "+Z",
      along: "+X",
    };
    const read = fromToml(toml({}, "foot.py", [], reference));
    expect(read).toEqual({ ok: true, values: {}, reference });
  });

  it("names the line it cannot read, in [reference]'s own words", () => {
    const bad = (line: string): string => {
      const found = fromToml(["[reference]", line].join("\n"));
      return found.ok ? "" : found.problem;
    };
    expect(bad("origin = [1, 2]")).toBe(
      "line 2: origin is not a number, a string, true/false or a triple",
    );
    expect(bad("origin = [1, 2, 3, 4]")).toBe(
      "line 2: origin is not a number, a string, true/false or a triple",
    );
    expect(bad("origin = [1, 2, x]")).toBe(
      "line 2: origin is not a number, a string, true/false or a triple",
    );
    expect(bad("origin = [1, 2, 3")).toBe(
      "line 2: origin is not a number, a string, true/false or a triple",
    );
  });
});
