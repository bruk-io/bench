import { describe, expect, it } from "vitest";

import { asBuilt, declaredOnly, parsed, withOverride } from "./overrides";
import type { ParamView } from "./scene";

const param = (name: string): ParamView => ({
  name,
  label: name,
  kind: "int",
  default: 1,
  min: null,
  max: null,
  step: null,
  choices: null,
});

describe("parsed", () => {
  it("is empty for nothing stored", () => {
    expect(parsed(null)).toEqual({});
  });

  it("is empty for something that is not JSON", () => {
    expect(parsed("{not json")).toEqual({});
  });

  it("is empty for JSON that is not an object", () => {
    expect(parsed("[1, 2]")).toEqual({});
    expect(parsed("7")).toEqual({});
    expect(parsed("null")).toEqual({});
  });

  it("keeps scalars and drops anything else", () => {
    expect(parsed('{"a": 1, "b": true, "c": "x", "d": null, "e": [1], "f": {}}')).toEqual({
      a: 1,
      b: true,
      c: "x",
    });
  });
});

describe("withOverride", () => {
  it("sets the value on a new table and leaves the old one alone", () => {
    const before = { a: 1 };
    const after = withOverride(before, "b", 2);
    expect(after).toEqual({ a: 1, b: 2 });
    expect(before).toEqual({ a: 1 });
  });

  it("replaces a value already set", () => {
    expect(withOverride({ a: 1 }, "a", 5)).toEqual({ a: 5 });
  });
});

describe("declaredOnly", () => {
  it("drops the names nobody declares", () => {
    expect(declaredOnly({ a: 1, gone: 2 }, [param("a")])).toEqual({ a: 1 });
  });

  it("hands back the very same table when nothing goes, so a caller can tell", () => {
    const table = { a: 1 };
    expect(declaredOnly(table, [param("a"), param("b")])).toBe(table);
  });

  it("prunes nothing against a script that declares no parameters", () => {
    const table = { a: 1 };
    expect(declaredOnly(table, [])).toBe(table);
  });
});

describe("asBuilt", () => {
  it("writes back what the run held to its range, and rounded", () => {
    expect(asBuilt({ units_x: 9, kerf: 2.5 }, { units_x: 7, kerf: 2, other: 1 })).toEqual({
      units_x: 7,
      kerf: 2,
    });
  });

  it("hands back the very same table when the run built every value as sent", () => {
    const table = { a: 1, b: "x", c: true };
    expect(asBuilt(table, { a: 1, b: "x", c: true, d: 4 })).toBe(table);
  });

  it("keeps a value the run did not report", () => {
    const table = { a: 1 };
    expect(asBuilt(table, {})).toBe(table);
  });
});
