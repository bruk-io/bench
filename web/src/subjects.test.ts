import { describe, expect, it } from "vitest";

import type { PartView, ViolationView } from "./scene";
import {
  PROJECT,
  findingsNaming,
  findingsOn,
  findingsOnNoPart,
  fitIdentifier,
  fitLine,
  keptAcross,
  linkOf,
  linked,
  linkedIn,
  partOf,
  partRefOf,
  standingOf,
  standingWords,
  subjectOf,
  worstPart,
  worstPlace,
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
  sights: {},
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

describe("worstPlace", () => {
  it("is the worst part and the first place on it of its first error", () => {
    const found = [
      finding("warning", ["tote/w"]),
      finding("error", ["lid/x", "tote/e1", "tote/e2"]),
      finding("error", ["tote/e3"]),
    ];
    expect(worstPlace(PARTS, found)).toEqual({ part: "tote", place: "tote/e1" });
  });

  it("is the first warning's first place when the worst part has no error", () => {
    expect(worstPlace(PARTS, [finding("unchecked", ["tote/u"]), finding("warning", ["tote/a", "tote/b"])])).toEqual({
      part: "tote",
      place: "tote/a",
    });
  });

  it("lights the part itself when its finding names nothing on it but the part", () => {
    expect(worstPlace(PARTS, [finding("error", ["tote"])])).toEqual({ part: "tote", place: "tote" });
  });

  it("is nowhere when no part is worse off than ok", () => {
    expect(worstPlace(PARTS, [finding("unchecked", ["lid/a"])])).toBeNull();
    expect(worstPlace(PARTS, [finding("error", ["gone/a"])])).toBeNull();
  });
});

describe("keptAcross", () => {
  const REFS = ["lid", "lid/top", "tote", "tote/wall-0", "tote/socket-1", "tote-latch"];

  it("keeps a part the run still makes, and the place lit on it", () => {
    const selection = { subject: { kind: "part", ref: "tote" }, lit: "tote/socket-1" } as const;
    expect(keptAcross(selection, PARTS, REFS)).toEqual(selection);
  });

  it("keeps the part and lights it when only the lit place is gone", () => {
    const selection = { subject: { kind: "part", ref: "tote" }, lit: "tote/socket-9" } as const;
    expect(keptAcross(selection, PARTS, REFS)).toEqual({ subject: { kind: "part", ref: "tote" }, lit: "tote" });
  });

  it("goes back to the project when the part is no longer made", () => {
    const selection = { subject: { kind: "part", ref: "drawer-6" }, lit: "drawer-6" } as const;
    expect(keptAcross(selection, PARTS, REFS)).toEqual({ subject: PROJECT, lit: null });
  });

  it("keeps a face the run still names", () => {
    const selection = { subject: { kind: "face", ref: "tote/wall-0" }, lit: "tote/wall-0" } as const;
    expect(keptAcross(selection, PARTS, REFS)).toEqual(selection);
  });

  it("goes back to the project, not to the face's part, when the face is gone", () => {
    const selection = { subject: { kind: "face", ref: "tote/wall-9" }, lit: "tote/wall-9" } as const;
    expect(keptAcross(selection, PARTS, REFS)).toEqual({ subject: PROJECT, lit: null });
  });

  it("keeps the project, and a place lit on it only while the run names it", () => {
    expect(keptAcross({ subject: PROJECT, lit: null }, PARTS, REFS)).toEqual({ subject: PROJECT, lit: null });
    expect(keptAcross({ subject: PROJECT, lit: "lid/top" }, PARTS, REFS)).toEqual({ subject: PROJECT, lit: "lid/top" });
    expect(keptAcross({ subject: PROJECT, lit: "lid/gone" }, PARTS, REFS)).toEqual({ subject: PROJECT, lit: null });
  });

  it("leaves a reference mesh alone: a run does not take it off the view", () => {
    const selection = { subject: { kind: "reference", file: "foot.stl" }, lit: null } as const;
    expect(keptAcross(selection, [], [])).toEqual(selection);
  });

  it("keeps a part with no ref of its own in the run's list - a part is named by being made", () => {
    const selection = { subject: { kind: "part", ref: "tote-latch" }, lit: "tote-latch" } as const;
    expect(keptAcross(selection, PARTS, [])).toEqual(selection);
  });
});

describe("linkOf and linked", () => {
  it("names a part or a face in the hash, with its slashes left as they read", () => {
    expect(linkOf({ kind: "part", ref: "tote" })).toBe("#part=tote");
    expect(linkOf({ kind: "face", ref: "tote/grip-left/top" })).toBe("#face=tote/grip-left/top");
  });

  it("leaves the project and a reference mesh out of the hash", () => {
    expect(linkOf(PROJECT)).toBe("");
    expect(linkOf({ kind: "reference", file: "foot.stl" })).toBe("");
  });

  it("round-trips a ref with characters a URL escapes", () => {
    for (const subject of [
      { kind: "part", ref: "drawer front #2" },
      { kind: "face", ref: "a=b/c%d/\u00e9" },
    ] as const) {
      expect(linked(linkOf(subject))).toEqual(subject);
    }
    expect(linkOf({ kind: "part", ref: "drawer front #2" })).toBe("#part=drawer%20front%20%232");
  });

  it("reads a hash with or without its #", () => {
    expect(linked("#part=tote")).toEqual({ kind: "part", ref: "tote" });
    expect(linked("face=tote/top")).toEqual({ kind: "face", ref: "tote/top" });
  });

  it("asks for nothing from a hash it does not know", () => {
    for (const hash of ["", "#", "#tote", "#view=tote", "#part=", "#part=%E0%A4%A", "#project=tote"]) {
      expect(linked(hash)).toBeNull();
    }
  });
});

describe("linkedIn", () => {
  const REFS = ["tote", "tote/grip-left/top"];

  it("is the subject a link asks for, when the run has it", () => {
    expect(linkedIn({ kind: "part", ref: "tote" }, PARTS, REFS)).toEqual({ kind: "part", ref: "tote" });
    expect(linkedIn({ kind: "face", ref: "tote/grip-left/top" }, PARTS, REFS)).toEqual({
      kind: "face",
      ref: "tote/grip-left/top",
    });
  });

  it("reads the ref as the run does, whatever the link called it", () => {
    expect(linkedIn({ kind: "face", ref: "tote" }, PARTS, REFS)).toEqual({ kind: "part", ref: "tote" });
  });

  it("is the project, quietly, for a ref the run does not have or no ask at all", () => {
    expect(linkedIn({ kind: "part", ref: "drawer-6" }, PARTS, REFS)).toEqual(PROJECT);
    expect(linkedIn({ kind: "face", ref: "tote/gone" }, PARTS, REFS)).toEqual(PROJECT);
    expect(linkedIn(null, PARTS, REFS)).toEqual(PROJECT);
  });
});
