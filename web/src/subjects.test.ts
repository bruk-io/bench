import { describe, expect, it } from "vitest";

import type { PartView, ViolationView } from "./scene";
import {
  PROJECT,
  findingsNaming,
  findingsOn,
  findingsOnNoPart,
  fitIdentifier,
  fitLine,
  partOf,
  partRefOf,
  standingOf,
  standingWords,
  subjectOf,
  worstPart,
} from "./subjects";

const part = (ref: string, fields: Partial<PartView> = {}): PartView => ({
  ref,
  label: ref,
  qty: 1,
  stock: { thickness: 0, material: "PLA", kerf: 0 },
  process: "print",
  bbox: [0, 0, 0, 10, 10, 10],
  mesh: null,
  marks: null,
  lettering: [],
  frames: {},
  areas: {},
  printing: null,
  ...fields,
});

const finding = (severity: ViolationView["severity"], refs: readonly string[], check = "wall"): ViolationView => ({
  check,
  message: `${check} found something`,
  severity,
  refs,
  line: 3,
});

const PARTS = [part("lid"), part("tote"), part("tote-latch")];

describe("subjectOf", () => {
  it("is the project while nothing is selected", () => {
    expect(subjectOf(null, PARTS)).toEqual(PROJECT);
  });

  it("is the part when the ref is a part's own", () => {
    expect(subjectOf("tote", PARTS)).toEqual({ kind: "part", ref: "tote" });
  });

  it("is a face for any other ref, known to a part or not", () => {
    expect(subjectOf("tote/wall-0", PARTS)).toEqual({ kind: "face", ref: "tote/wall-0" });
    expect(subjectOf("gone/wall-0", PARTS)).toEqual({ kind: "face", ref: "gone/wall-0" });
  });
});

describe("partOf", () => {
  it("finds the part a face is on by its path, not by a shared prefix", () => {
    expect(partOf("tote-latch/lug", PARTS)?.ref).toBe("tote-latch");
    expect(partOf("tote/lug", PARTS)?.ref).toBe("tote");
    expect(partOf("toter/lug", PARTS)).toBeNull();
  });

  it("takes the nearest part when one part's ref sits under another's", () => {
    expect(partOf("tote/lid/rim", [part("tote"), part("tote/lid")])?.ref).toBe("tote/lid");
  });

  it("names the part a subject is about", () => {
    expect(partRefOf({ kind: "face", ref: "lid/rim" }, PARTS)).toBe("lid");
    expect(partRefOf({ kind: "part", ref: "lid" }, PARTS)).toBe("lid");
    expect(partRefOf(PROJECT, PARTS)).toBeNull();
    expect(partRefOf({ kind: "reference", file: "foot.stl" }, PARTS)).toBeNull();
  });
});

describe("findings, sorted by what they are about", () => {
  const wall = finding("error", ["lid/wall-0"]);
  const fits = finding("warning", ["lid/rim", "tote/socket"], "fits");
  const nowhere = finding("unchecked", [], "overhangs");
  const all = [wall, fits, nowhere];

  it("puts a finding on every part one of its places is on", () => {
    expect(findingsOn("lid", all)).toEqual([wall, fits]);
    expect(findingsOn("tote", all)).toEqual([fits]);
    expect(findingsOn("tote-latch", all)).toEqual([]);
  });

  it("gives a face the findings that name it or something inside it", () => {
    expect(findingsNaming("lid/rim", all)).toEqual([fits]);
    expect(findingsNaming("lid/wall-0", all)).toEqual([wall]);
  });

  it("leaves a finding with nowhere to point to the project", () => {
    expect(findingsOnNoPart(all, PARTS)).toEqual([nowhere]);
    expect(findingsOnNoPart([finding("warning", ["gone/face"])], PARTS)).toHaveLength(1);
  });
});

describe("standingOf", () => {
  it("is the worst severity found, counted", () => {
    expect(standingOf([finding("warning", []), finding("error", []), finding("error", [])])).toEqual({
      kind: "error",
      count: 2,
    });
    expect(standingOf([finding("warning", []), finding("unchecked", [])])).toEqual({ kind: "warning", count: 1 });
  });

  it("never reads 'not checked' as a pass", () => {
    expect(standingOf([finding("unchecked", [])])).toEqual({ kind: "unchecked" });
    expect(standingWords({ kind: "unchecked" })).toBe("not checked");
  });

  it("is ok with nothing found, and says each standing in words", () => {
    expect(standingOf([])).toEqual({ kind: "ok" });
    expect(standingWords({ kind: "ok" })).toBe("ok");
    expect(standingWords({ kind: "error", count: 1 })).toBe("1 error");
    expect(standingWords({ kind: "warning", count: 3 })).toBe("3 warnings");
  });
});

describe("worstPart", () => {
  it("is the part with the most errors before any with warnings", () => {
    const found = [finding("warning", ["lid/a"]), finding("warning", ["lid/b"]), finding("error", ["tote/c"])];
    expect(worstPart(PARTS, found)).toBe("tote");
  });

  it("is the part with the most warnings when none has an error, the first between two alike", () => {
    expect(worstPart(PARTS, [finding("warning", ["tote/a"]), finding("warning", ["tote/b"]), finding("warning", ["lid/a"])])).toBe(
      "tote",
    );
    expect(worstPart(PARTS, [finding("warning", ["tote/a"]), finding("warning", ["lid/a"])])).toBe("lid");
  });

  it("is nobody when only what nothing measured, or nothing, was found", () => {
    expect(worstPart(PARTS, [finding("unchecked", ["lid/a"])])).toBeNull();
    expect(worstPart(PARTS, [])).toBeNull();
  });
});

describe("fitLine", () => {
  const frame = { origin: [0, 0, 0], normal: [0, 0, 1], x: [1, 0, 0] } as const;
  const printed = [
    part("base", { frames: { "base/top": frame } }),
    part("2-lid", { frames: { "2-lid/bottom": frame } }),
    part("panel", { process: "laser" }),
  ];

  it("writes the mated line for two framed faces on two printed parts", () => {
    expect(fitLine("base/top", "2-lid/bottom", printed)).toEqual({
      text: 'mated(base, ref("base/top"), _2_lid, ref("2-lid/bottom"))',
    });
  });

  it("says why a pair cannot be written", () => {
    expect(fitLine("base/top", "panel/edge", printed)).toEqual({
      why: "mated puts one printed part's face on another's; a sheet part has none",
    });
    expect("why" in fitLine("base/side", "2-lid/bottom", printed)).toBe(true);
  });

  it("says nothing while there is no pair", () => {
    expect(fitLine("base/top", null, printed)).toEqual({ why: "" });
  });

  it("turns a ref into the identifier a maker would have typed", () => {
    expect(fitIdentifier("drawer-front-1")).toBe("drawer_front_1");
    expect(fitIdentifier("3d-thing")).toBe("_3d_thing");
  });
});
