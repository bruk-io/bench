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
        areas: { "plate/hole": 12.5 },
        printing: null,
        ...part,
      },
    ],
    stage: { bounds: [0, 0, 0, 10, 10, 3] },
    summary: { parts: 1, sheets: 0, errors: 0, warnings: 0, error_line: null, solid: 1, unbuilt: 0, printed: 0 },
    refs: ["plate", "plate/hole", "plate/score", "plate/label"],
    sheets: [],
    files: {},
    violations: [],
    warnings: [],
    stdout: "",
    stderr: "",
    reference: null,
    context: [],
    bed: null,
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

describe("received, bodies shown for context", () => {
  /** The plate's four buffers, then one triangle of a pin's, naming its one face. */
  const withPin = (): unknown[] => [...buffers(), new Float32Array(9), new Uint32Array([1])];

  it("puts a context body's buffers back on it, under its own ref", () => {
    const shown = wire();
    shown["context"] = [
      { ref: "pin", mesh: { positions: 4, ref_index: 5, refs: ["pin/top"] } },
      { ref: "ghost", mesh: null },
    ];
    const found = received(shown, withPin());
    if (!("scene" in found) || !found.scene.ok) throw new Error("that scene was meant to be read");
    const [pin, ghost] = found.scene.context;
    expect(pin?.ref).toBe("pin");
    expect(pin?.mesh?.positions).toBeInstanceOf(Float32Array);
    expect(pin?.mesh?.refs).toEqual(["pin/top"]);
    expect(ghost).toEqual({ ref: "ghost", mesh: null });
    expect(found.scene.parts).toHaveLength(1);
  });

  it("reads a scene that shows no context", () => {
    expect(problemOf(wire())).toBeNull();
  });

  it("refuses a scene with no context list at all", () => {
    const old = wire();
    delete old["context"];
    expect(problemOf(old)).toBe("context is not an array");
  });

  it("refuses a context body whose mesh names a ref it does not carry", () => {
    const shown = wire();
    shown["context"] = [{ ref: "pin", mesh: { positions: 4, ref_index: 5, refs: [] } }];
    expect(problemOf(shown, withPin())).toBe("context[0] (pin).mesh names a ref it does not carry");
  });
});

describe("received, how a printed part prints and the bed it is laid on", () => {
  const PRINTING = {
    up: [0, 0, -1],
    bed_face: "plate/top",
    fits: false,
    over: "the part is bigger than the build volume: x 400.0 mm against 350.0 mm",
    placement: [1, 0, 0, 10, 0, 1, 0, 20, 0, 0, 1, 0],
  };
  const BED = {
    printer: "H2D",
    said: "host",
    volume: [350, 320, 325],
    bounds: [0, 0, 0, 350, 320, 325],
    plates: 1,
    floor: [0, 0, 0, 0, 320, 0],
    edges: [0, 0, 0, 350, 0, 0],
  };

  it("reads a part's printing and face areas, and the bed, as Python sent them", () => {
    const shown = wire({ printing: PRINTING });
    shown["bed"] = BED;
    const found = received(shown, buffers());
    if (!("scene" in found) || !found.scene.ok) throw new Error("that scene was meant to be read");
    expect(found.scene.parts[0]?.printing).toEqual(PRINTING);
    expect(found.scene.parts[0]?.areas).toEqual({ "plate/hole": 12.5 });
    expect(found.scene.bed).toEqual(BED);
  });

  it("reads a printed part with no body and no bed to lay it on", () => {
    expect(problemOf(wire({ printing: { ...PRINTING, fits: null, over: null, placement: null } }))).toBeNull();
  });

  it("refuses a placement that is not three rows of four", () => {
    expect(problemOf(wire({ printing: { ...PRINTING, placement: [1, 0, 0, 0, 1, 0, 0, 0, 1] } }))).toBe(
      "parts[0] (plate).printing.placement is not twelve numbers or null",
    );
  });

  it("refuses an area that is not a number", () => {
    expect(problemOf(wire({ areas: { "plate/hole": "big" } }))).toBe(
      'parts[0] (plate).areas["plate/hole"] is not a number',
    );
  });

  it("refuses a bed whose floor is not whole lines", () => {
    const shown = wire();
    shown["bed"] = { ...BED, floor: [0, 0, 0, 0, 320] };
    expect(problemOf(shown)).toBe("bed.floor is not six numbers per line");
  });

  it("refuses a scene with no bed key at all", () => {
    const old = wire();
    delete old["bed"];
    expect(problemOf(old)).toBe("bed is absent");
  });
});
