import { describe, expect, it } from "vitest";

import { received } from "./scene";

/** A whole ok scene on the wire, with one part whose lists are in `buffers`. */
function wire(part: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    ok: true,
    params: [],
    values: {},
    parts: [
      {
        ref: "plate",
        label: "plate",
        qty: 1,
        stock: { thickness: 3, material: "ply", kerf: 0.25 },
        process: "laser",
        bbox: [0, 0, 10, 10],
        mesh: { positions: 0, ref_index: 1, refs: ["plate/hole"] },
        marks: { segments: 2, ref_index: 3, refs: ["plate/score"] },
        lettering: [{ text: "1", ref: "plate/label", corners: Array.from({ length: 12 }, () => 0) }],
        frames: {},
        ...part,
      },
    ],
    stage: { bounds: [0, 0, 0, 10, 10, 3], grid: { size: 20, divisions: 2, centre: [5, 5] } },
    summary: { parts: 1, sheets: 0, errors: 0, warnings: 0, error_line: null, solid: 1, unbuilt: 0 },
    refs: ["plate", "plate/hole", "plate/score", "plate/label"],
    sheets: [],
    files: {},
    violations: [],
    warnings: [],
    stdout: "",
    stderr: "",
    reference: null,
  };
}

/** One triangle and one segment, both naming their first ref. */
const buffers = (): unknown[] => [
  new Float32Array(9),
  new Uint32Array([1]),
  new Float32Array(6),
  new Uint32Array([1]),
];

const problemOf = (value: unknown, given: unknown = buffers()): string | null => {
  const found = received(value, given);
  return "problem" in found ? found.problem : null;
};

describe("received, plates and what is engraved on them", () => {
  it("puts a mesh's and its marks' buffers back on the part", () => {
    const found = received(wire(), buffers());
    if (!("scene" in found) || !found.scene.ok) throw new Error("that scene was meant to be read");
    const [part] = found.scene.parts;
    expect(part?.mesh?.positions).toBeInstanceOf(Float32Array);
    expect(part?.marks?.segments).toBeInstanceOf(Float32Array);
    expect(part?.marks?.refs).toEqual(["plate/score"]);
    expect(part?.lettering[0]?.text).toBe("1");
  });

  it("reads a part with no body and nothing engraved", () => {
    expect(problemOf(wire({ mesh: null, marks: null, lettering: [] }), [])).toBeNull();
  });

  it("refuses marks whose segments and refs disagree in count", () => {
    const short = [new Float32Array(9), new Uint32Array([1]), new Float32Array(5), new Uint32Array([1])];
    expect(problemOf(wire(), short)).toContain("marks has");
  });

  it("refuses marks that name a ref they do not carry", () => {
    const beyond = [new Float32Array(9), new Uint32Array([1]), new Float32Array(6), new Uint32Array([2])];
    expect(problemOf(wire(), beyond)).toContain("marks names a ref it does not carry");
  });

  it("refuses lettering without its twelve corners", () => {
    expect(problemOf(wire({ lettering: [{ text: "1", ref: null, corners: [0, 0, 0] }]}))).toContain(
      "corners is not twelve numbers",
    );
  });

  it("refuses a summary that still counts parts by pane", () => {
    const old = wire();
    old["summary"] = { parts: 1, sheets: 0, errors: 0, warnings: 0, error_line: null, drawn: 1 };
    expect(problemOf(old)).toBe("summary.solid is not a whole number");
  });

  it("reads a face's frame - origin, normal, x - onto the part", () => {
    const found = received(
      wire({ frames: { "plate/hole": { origin: [1, 2, 3], normal: [0, 0, 1], x: [1, 0, 0] } } }),
      buffers(),
    );
    if (!("scene" in found) || !found.scene.ok) throw new Error("that scene was meant to be read");
    expect(found.scene.parts[0]?.frames["plate/hole"]).toEqual({
      origin: [1, 2, 3],
      normal: [0, 0, 1],
      x: [1, 0, 0],
    });
  });

  it("refuses a frame with the wrong count of numbers", () => {
    const bad = wire({ frames: { "plate/hole": { origin: [1, 2], normal: [0, 0, 1], x: [1, 0, 0] } } });
    expect(problemOf(bad)).toContain("frames");
  });
});
