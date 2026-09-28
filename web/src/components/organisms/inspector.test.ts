import { afterEach, describe, expect, it } from "vitest";

import type { BedView, FrameView, ParamView, PartView, SheetView, ViolationView } from "../../scene";
import { type Subject, keptAcross, worstPlace } from "../../subjects";
import type { BenchViolation } from "../molecules/violation";
import "./inspector";
import type { BenchInspector } from "./inspector";
import type { ReferenceToolsView } from "./reference-tools";

const FRAME: FrameView = { origin: [0, 0, 20], normal: [0, 0, 1], x: [1, 0, 0] };

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

const TOTE = part("tote", {
  frames: { "tote/floor": FRAME },
  areas: { "tote/floor": 1234.56 },
  printing: { up: [0, 0, 1], bed_face: null, fits: true, over: null, placement: null },
});
const LID = part("lid", {
  printing: {
    up: [0, -1, 0],
    bed_face: "lid/rim",
    fits: false,
    over: "the part is bigger than the build volume: x 400.0 mm against 350.0 mm",
    placement: null,
  },
});

const H2D: BedView = {
  printer: "H2D",
  said: "host",
  volume: [350, 320, 325],
  bounds: [0, 0, 0, 350, 320, 325],
  plates: 1,
  floor: [],
  edges: [],
};
const PANEL = part("panel", { process: "laser", qty: 2, stock: { thickness: 3, material: "ply", kerf: 0.2 } });

const REFS = ["tote", "tote/floor", "tote/wall-0", "tote/lug-1", "lid", "lid/rim", "panel", "panel/edge"];

const OVERHANGS: ViolationView = {
  check: "overhangs",
  message: "2 places lean further off the build direction than PLA holds up 45 degrees: tote/lug-1 leans 90 degrees; tote/floor leans 90 degrees",
  severity: "warning",
  refs: ["tote/lug-1", "tote/floor"],
  line: 30,
};

const WALL: ViolationView = { check: "wall", message: "thinnest wall is 0.6 mm", severity: "error", refs: ["lid/rim"], line: 12 };

const NOWHERE: ViolationView = { check: "fits", message: "no kernel to measure with", severity: "unchecked", refs: [], line: 8 };

const SHEET: SheetView = { name: "sheet-3mm-01", thickness: 3, svg: "<svg/>", preview: "<svg/>", parts: ["panel", "panel"] };

const FILES = { "sheet-3mm-01.svg": "<svg/>", "tote.stl": btoa("\0".repeat(84)), "part-panel.svg": "<svg/>", "tote.3mf": "AAAA" };

const PARAMS: readonly ParamView[] = [
  { name: "wall", label: "Wall", kind: "float", default: 2, min: 1, max: 5, step: 0.1, choices: null },
];

const TOOLS: ReferenceToolsView = {
  chip: "foot.stl · placed",
  chipTitle: "",
  survey: "ready",
  detecting: false,
  detectWaiting: false,
  pick: null,
  said: "",
};

type Fields = Partial<
  Pick<
    BenchInspector,
    | "subject"
    | "project"
    | "parts"
    | "refs"
    | "violations"
    | "warnings"
    | "sheets"
    | "files"
    | "bed"
    | "error"
    | "params"
    | "overrides"
    | "reading"
    | "hiddenRefs"
    | "lit"
    | "insertable"
    | "fit"
    | "second"
    | "references"
    | "activeReference"
    | "tools"
  >
>;

const RUN: Fields = {
  project: "tote",
  parts: [TOTE, LID, PANEL],
  refs: REFS,
  violations: [OVERHANGS, WALL, NOWHERE],
  warnings: [],
  sheets: [SHEET],
  files: FILES,
  bed: H2D,
  params: PARAMS,
};

async function mounted(fields: Fields = {}): Promise<BenchInspector> {
  const inspector = document.createElement("bench-inspector");
  Object.assign(inspector, RUN, fields);
  document.body.append(inspector);
  await inspector.updateComplete;
  return inspector;
}

async function given(inspector: BenchInspector, fields: Fields): Promise<void> {
  Object.assign(inspector, fields);
  await inspector.updateComplete;
}

const inside = <T extends Element = HTMLElement>(inspector: BenchInspector, selector: string): T | null =>
  inspector.shadowRoot?.querySelector<T>(selector) ?? null;

const sections = (inspector: BenchInspector): string[] =>
  Array.from(inspector.shadowRoot?.querySelectorAll(".body > section") ?? [], (section) => section.id);

/** Every `type` event the inspector lets out while `act` runs. */
function caught<T>(inspector: BenchInspector, type: string, act: () => void): T[] {
  const seen: T[] = [];
  const listener = (event: Event): void => {
    seen.push((event as CustomEvent<T>).detail);
  };
  inspector.addEventListener(type, listener);
  act();
  inspector.removeEventListener(type, listener);
  return seen;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-inspector, with nothing selected: the project", () => {
  it("shows the knobs, the parts, what is on no one part and the export, and no faces", async () => {
    const inspector = await mounted();
    expect(sections(inspector)).toEqual(["knobs", "parts", "project-findings", "export"]);
    expect(inside(inspector, "#crumb-project")?.textContent.trim()).toBe("tote");
    expect(inside(inspector, "bench-refs-tree")).toBeNull();
  });

  it("hands the knobs the declarations and the overrides, and counts them", async () => {
    const inspector = await mounted({ overrides: { wall: 3 } });
    const params = inside(inspector, "bench-params");
    expect(params).not.toBeNull();
    expect(inside(inspector, "#param-count")?.textContent).toBe("1");
    expect(inside<HTMLButtonElement>(inspector, "#reset")?.disabled).toBe(false);
  });

  it("asks for the knobs to be reset, and offers it only when something was turned", async () => {
    const clean = await mounted();
    expect(inside<HTMLButtonElement>(clean, "#reset")?.disabled).toBe(true);
    const turned = await mounted({ overrides: { wall: 3 } });
    const asked = caught(turned, "params-reset", () => inside(turned, "#reset")?.click());
    expect(asked).toHaveLength(1);
  });

  it("says a turned knob is not kept while the project is only being read", async () => {
    const inspector = await mounted({ reading: true });
    expect(inside(inspector, "#params-unkept")?.textContent).toContain("nothing turned is kept");
  });

  it("gives every part a badge for how it stands - errors, warnings, not checked or ok", async () => {
    const inspector = await mounted();
    const badges = Array.from(inspector.shadowRoot?.querySelectorAll<HTMLElement>(".part") ?? [], (row) => [
      row.dataset["part"],
      row.querySelector<HTMLElement>(".badge")?.dataset["standing"],
      row.querySelector(".badge")?.textContent,
    ]);
    expect(badges).toEqual([
      ["tote", "warning", "1 warning"],
      ["lid", "error", "1 error"],
      ["panel", "ok", "ok"],
    ]);
  });

  it("says what a part is made of and how many", async () => {
    const inspector = await mounted();
    const meta = inside(inspector, '.part[data-part="panel"] .part-meta')?.textContent;
    expect(meta).toBe("laser · 3 mm ply × 2");
  });

  it("asks for a part to be the subject when its row is clicked, and never selects it itself", async () => {
    const inspector = await mounted();
    const asked = caught<Subject>(inspector, "subject-pick", () => inside(inspector, '.part[data-part="lid"]')?.click());
    expect(asked).toEqual([{ kind: "part", ref: "lid" }]);
    expect(inspector.subject).toEqual({ kind: "project" });
  });

  it("keeps the findings that are about no one part, and the nest's warnings, with the project", async () => {
    const inspector = await mounted({ warnings: ["part too big for the bed"] });
    const rows = inside(inspector, "#project-findings bench-violation-list")?.shadowRoot?.querySelectorAll<BenchViolation>(
      "bench-violation",
    );
    expect(Array.from(rows ?? [], (row) => row.check)).toEqual(["fits"]);
    expect(inside(inspector, "#warnings li")?.textContent).toBe("part too big for the bed");
  });

  it("lists the reference meshes the project holds, and lets a choice out", async () => {
    const inspector = await mounted({ references: ["foot.stl"], activeReference: "foot.stl" });
    expect(sections(inspector)).toContain("references");
    const list = inside(inspector, "bench-reference-list");
    await (list as unknown as { updateComplete: Promise<unknown> } | null)?.updateComplete;
    const asked = caught<{ file: string }>(inspector, "reference-pick", () => {
      list?.shadowRoot?.querySelector<HTMLElement>('[data-reference="foot.stl"]')?.click();
    });
    expect(asked).toEqual([{ file: "foot.stl" }]);
  });

  it("exports everything, with Download all", async () => {
    const inspector = await mounted();
    const exports = inside(inspector, "bench-exports");
    expect((exports as unknown as { onlyPart: unknown } | null)?.onlyPart).toBeNull();
  });

  it("says how to select something, and offers no Insert ref for nothing", async () => {
    const inspector = await mounted();
    expect(inside(inspector, "#selection")?.textContent).toBe("click any face to get its ref");
    expect(inside<HTMLButtonElement>(inspector, "#insert")?.disabled).toBe(true);
  });
});

describe("bench-inspector, a part", () => {
  const TOTE_SUBJECT: Fields = { subject: { kind: "part", ref: "tote" }, lit: "tote", insertable: true };

  it("shows the knobs folded, its findings, how it is made, its faces and its own export", async () => {
    const inspector = await mounted(TOTE_SUBJECT);
    expect(sections(inspector)).toEqual(["knobs", "part-findings", "prints", "faces", "export"]);
    expect(inside(inspector, "#crumb-part")?.textContent.trim()).toBe("tote");
    expect(inside(inspector, "#export-head")?.textContent.trim()).toBe("Export this part");
    expect(inside(inspector, "#knobs-fold")?.getAttribute("aria-expanded")).toBe("false");
  });

  it("lists each finding's places, and asks for one to be lit rather than leaving the part", async () => {
    const inspector = await mounted(TOTE_SUBJECT);
    const list = inside(inspector, "#part-findings bench-violation-list");
    const [row] = Array.from(list?.shadowRoot?.querySelectorAll<BenchViolation>("bench-violation") ?? []);
    await row?.updateComplete;
    const places = Array.from(row?.shadowRoot?.querySelectorAll(".place") ?? [], (one) => one.textContent.trim());
    expect(places).toEqual(["tote/lug-1", "tote/floor"]);
    const asked = caught<{ ref: string }>(inspector, "place-pick", () => {
      row?.shadowRoot?.querySelector<HTMLButtonElement>('.place[data-ref="tote/floor"]')?.click();
    });
    expect(asked).toEqual([{ ref: "tote/floor" }]);
  });

  it("marks the place the page lit", async () => {
    const inspector = await mounted({ ...TOTE_SUBJECT, lit: "tote/floor" });
    const list = inside(inspector, "#part-findings bench-violation-list");
    await (list as unknown as { updateComplete: Promise<unknown> } | null)?.updateComplete;
    const [row] = Array.from(list?.shadowRoot?.querySelectorAll<BenchViolation>("bench-violation") ?? []);
    await row?.updateComplete;
    expect(row?.shadowRoot?.querySelector('.place[aria-current="true"]')?.textContent.trim()).toBe("tote/floor");
    // The inspector stays on the part: a lit place is not a new subject.
    expect(inside(inspector, "#crumb-part")?.getAttribute("aria-current")).toBe("page");
  });

  it("says so in how it is made when nothing was reported about the part, with no empty findings", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "panel" } });
    expect(sections(inspector)).not.toContain("part-findings");
    expect(inside(inspector, "#prints #no-problems")?.textContent).toContain("nothing was reported");
    expect(inside<HTMLElement>(inspector, "#prints .badge")?.dataset["standing"]).toBe("ok");
  });

  it("draws no faces for a part with no face of its own, and no export for a part with no file", async () => {
    const bare = part("bare", { process: "laser", stock: { thickness: 3, material: "ply", kerf: 0 } });
    const inspector = await mounted({ subject: { kind: "part", ref: "bare" }, parts: [bare], refs: ["bare"] });
    expect(sections(inspector)).toEqual(["knobs", "prints"]);
    expect(inside(inspector, "#export-reach")).toBeNull();
  });

  it("draws its faces as a tree of its own refs and nobody else's", async () => {
    const inspector = await mounted(TOTE_SUBJECT);
    const tree = inside(inspector, "bench-refs-tree") as unknown as { refs: readonly string[] } | null;
    expect(tree?.refs).toEqual(["tote", "tote/floor", "tote/wall-0", "tote/lug-1"]);
    expect(inside(inspector, "#refs-count")?.textContent).toBe("4");
  });

  it("goes back to the project from its breadcrumb", async () => {
    const inspector = await mounted(TOTE_SUBJECT);
    const asked = caught<Subject>(inspector, "subject-pick", () => inside(inspector, "#crumb-project")?.click());
    expect(asked).toEqual([{ kind: "project" }]);
  });

  it("offers Insert ref for the lit ref, and asks for it rather than writing it", async () => {
    const inspector = await mounted(TOTE_SUBJECT);
    expect(inside(inspector, "#selection")?.textContent).toBe("tote");
    const asked = caught(inspector, "insert-ref", () => inside(inspector, "#insert")?.click());
    expect(asked).toHaveLength(1);
  });

  it("says how a printed part prints - which way up, and that it fits the bed - in 'How it is made'", async () => {
    const inspector = await mounted(TOTE_SUBJECT);
    expect(inside(inspector, "#print-up")?.textContent.trim()).toBe("+Z up");
    const fits = inside(inspector, "#print-fits");
    expect(fits?.dataset["fits"]).toBe("true");
    expect(fits?.textContent.trim()).toBe("fits the H2D (350 × 320 × 325 mm)");
    expect(fits?.title).toContain("default printer");
  });

  it("says the face a part stands on, and why it does not fit", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "lid" } });
    expect(inside(inspector, "#print-up")?.textContent.trim()).toBe("−Y up, on rim");
    const fits = inside(inspector, "#print-fits");
    expect(fits?.dataset["fits"]).toBe("false");
    expect(fits?.textContent).toContain("does not fit the H2D");
    expect(fits?.querySelector(".over")?.textContent).toContain("x 400.0 mm against 350.0 mm");
  });

  it("says which volume a script asked about is the bed", async () => {
    const inspector = await mounted({
      ...TOTE_SUBJECT,
      bed: { ...H2D, printer: null, said: "script", volume: [256, 256, 256] },
    });
    expect(inside(inspector, "#print-fits")?.textContent.trim()).toBe("fits a 256 × 256 × 256 mm volume");
    expect(inside(inspector, "#print-fits")?.title).toContain("check_fits");
  });

  it("says a printed part has no bed to fit when nothing named a printer", async () => {
    const unasked = part("tote", { printing: { up: [0, 0, 1], bed_face: null, fits: null, over: null, placement: null } });
    const inspector = await mounted({ ...TOTE_SUBJECT, parts: [unasked], bed: null });
    expect(inside(inspector, "#print-fits")?.textContent.trim()).toBe("no printer named to fit it on");
  });

  it("says nothing about printing for a part that is cut", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "panel" } });
    expect(inside(inspector, "#print-up")).toBeNull();
    expect(inside(inspector, "#print-fits")).toBeNull();
  });

  it("says a part the newest run no longer makes is not there", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "gone" } });
    expect(inside(inspector, ".body")?.textContent).toContain("made no part called gone");
  });
});

describe("bench-inspector, a face", () => {
  const FLOOR: Fields = { subject: { kind: "face", ref: "tote/floor" }, lit: "tote/floor" };

  it("shows its ref, its part, its normal and the findings naming it - and no export", async () => {
    const inspector = await mounted(FLOOR);
    expect(sections(inspector)).toEqual(["knobs", "face", "face-findings", "faces"]);
    const said = inside(inspector, "#face dl")?.textContent ?? "";
    expect(said).toContain("tote/floor");
    expect(said).toContain("0.000, 0.000, 1.000");
    const list = inside(inspector, "#face-findings bench-violation-list") as unknown as {
      violations: readonly ViolationView[];
    } | null;
    expect(list?.violations).toEqual([OVERHANGS]);
  });

  it("draws no findings for a face no check named", async () => {
    const inspector = await mounted({ subject: { kind: "face", ref: "tote/wall-0" }, lit: "tote/wall-0" });
    expect(sections(inspector)).toEqual(["knobs", "face", "faces"]);
    expect(inside(inspector, ".body")?.textContent).not.toContain("No check named");
  });

  it("leaves out a normal the scene does not carry", async () => {
    const inspector = await mounted({ subject: { kind: "face", ref: "tote/wall-0" }, lit: "tote/wall-0" });
    expect(inside(inspector, "#face dl")?.textContent).not.toContain("normal");
  });

  it("shows the face's area as Python summed it", async () => {
    const inspector = await mounted(FLOOR);
    expect(inside(inspector, "#face-area")?.textContent).toBe("1234.6 mm²");
  });

  it("leaves out an area the scene does not carry", async () => {
    const inspector = await mounted({ subject: { kind: "face", ref: "tote/wall-0" }, lit: "tote/wall-0" });
    expect(inside(inspector, "#face-area")).toBeNull();
  });

  it("breadcrumbs through its part, and goes to the part from there", async () => {
    const inspector = await mounted(FLOOR);
    expect(inside(inspector, ".crumb-tail")?.textContent).toBe("floor");
    const asked = caught<Subject>(inspector, "subject-pick", () => inside(inspector, "#crumb-part")?.click());
    expect(asked).toEqual([{ kind: "part", ref: "tote" }]);
  });

  it("keeps the one faces tree when the subject moves from a part to one of its faces", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "tote" }, lit: "tote" });
    const before = inside(inspector, "bench-refs-tree");
    await given(inspector, FLOOR);
    const after = inside(inspector, "bench-refs-tree");
    expect(after).not.toBeNull();
    expect(after).toBe(before);
    expect((after as unknown as { selected: string | null }).selected).toBe("tote/floor");
  });

  it("says why a second pick cannot be written as a fit, and offers the fit when it can", async () => {
    const why = await mounted({ ...FLOOR, second: "panel/edge", fit: { why: "a sheet part has none" } });
    expect(inside(why, "#fit-why")?.textContent).toBe("a sheet part has none");
    expect(inside<HTMLButtonElement>(why, "#insert-fit")?.disabled).toBe(true);
    const text = 'mated(tote, ref("tote/floor"), lid, ref("lid/rim"))';
    const can = await mounted({ ...FLOOR, insertable: true, second: "lid/rim", fit: { text } });
    expect(inside<HTMLButtonElement>(can, "#insert-fit")?.disabled).toBe(false);
    expect(caught(can, "insert-fit", () => inside(can, "#insert-fit")?.click())).toHaveLength(1);
  });
});

describe("bench-inspector, a reference mesh", () => {
  it("shows the body's tools while it is the one on the view", async () => {
    const inspector = await mounted({
      subject: { kind: "reference", file: "foot.stl" },
      references: ["foot.stl"],
      activeReference: "foot.stl",
      tools: TOOLS,
    });
    expect(sections(inspector)).toEqual(["knobs", "reference-tools"]);
    const tools = inside(inspector, "bench-reference-tools");
    await (tools as unknown as { updateComplete: Promise<unknown> } | null)?.updateComplete;
    expect(tools?.shadowRoot?.querySelector("#reference-name")?.textContent).toBe("foot.stl · placed");
    expect(inside(inspector, "#selection")?.textContent).toBe("reference: foot.stl");
  });

  it("says a reference that is not the one on the view is not there", async () => {
    const inspector = await mounted({
      subject: { kind: "reference", file: "other.stl" },
      activeReference: "foot.stl",
      tools: TOOLS,
    });
    expect(inside(inspector, "bench-reference-tools")).toBeNull();
    expect(inside(inspector, "#reference-tools")?.textContent).toContain("not on the view");
  });
});

describe("bench-inspector, the knobs over every subject (task-94)", () => {
  const fold = (inspector: BenchInspector): HTMLButtonElement | null =>
    inside<HTMLButtonElement>(inspector, "#knobs-fold");
  const open = (inspector: BenchInspector): boolean => !(inside(inspector, "bench-params")?.hidden ?? true);

  it("opens on the project and folds on a part, a face and a reference, whose own sections lead", async () => {
    const inspector = await mounted();
    expect(open(inspector)).toBe(true);
    expect(fold(inspector)?.getAttribute("aria-expanded")).toBe("true");
    for (const subject of [
      { kind: "part", ref: "tote" },
      { kind: "face", ref: "tote/floor" },
      { kind: "reference", file: "foot.stl" },
    ] as const) {
      await given(inspector, { subject });
      expect(sections(inspector)[0]).toBe("knobs");
      expect(open(inspector)).toBe(false);
      expect(fold(inspector)?.getAttribute("aria-expanded")).toBe("false");
    }
  });

  it("unfolds on a part, and stays unfolded as the selection moves to one of its faces", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "tote" }, lit: "tote" });
    fold(inspector)?.click();
    await inspector.updateComplete;
    expect(open(inspector)).toBe(true);
    await given(inspector, { subject: { kind: "face", ref: "tote/floor" }, lit: "tote/floor" });
    expect(open(inspector)).toBe(true);
    // The project keeps its own: folding it there is not folding it on a part.
    await given(inspector, { subject: { kind: "project" }, lit: null });
    fold(inspector)?.click();
    await inspector.updateComplete;
    expect(open(inspector)).toBe(false);
    await given(inspector, { subject: { kind: "part", ref: "lid" }, lit: "lid" });
    expect(open(inspector)).toBe(true);
  });

  it("is one element across every subject, so a knob being typed in survives the selection moving", async () => {
    const inspector = await mounted();
    const before = inside(inspector, "bench-params");
    await given(inspector, { subject: { kind: "part", ref: "tote" }, lit: "tote" });
    await given(inspector, { subject: { kind: "face", ref: "tote/floor" }, lit: "tote/floor" });
    expect(inside(inspector, "bench-params")).toBe(before);
  });

  it("hands a turned knob up from a part, and lets it be reset there", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "tote" }, overrides: { wall: 3 } });
    expect(caught(inspector, "params-reset", () => inside(inspector, "#reset")?.click())).toHaveLength(1);
  });

  it("is not drawn before a run has declared any, nor for a script that declares none", async () => {
    const before = await mounted({ params: null });
    expect(sections(before)).not.toContain("knobs");
    const none = await mounted({ params: [] });
    expect(sections(none)).not.toContain("knobs");
  });
});

describe("bench-inspector, no section with nothing in it (task-94)", () => {
  it("draws no parts and no export before anything has run, and says nothing has", async () => {
    const inspector = await mounted({ parts: [], refs: [], violations: [], sheets: [], files: {}, params: null });
    expect(sections(inspector)).toEqual([]);
    expect(inside(inspector, "#nothing-ran")?.textContent).toContain("Nothing has run yet");
  });

  it("keeps the export's heading at the foot of the column, a click away from the export", async () => {
    const inspector = await mounted();
    const head = inside(inspector, ".export-head");
    expect(head === null ? "" : getComputedStyle(head).position).toBe("sticky");
    expect(head?.nextElementSibling?.id).toBe("export");
    expect(inside(inspector, "#export-reach")?.closest("h2")?.id).toBe("export-head");
    expect(inside(inspector, ".export-head .count")?.textContent).toBe("4 files");
  });
});

describe("bench-inspector, a run that failed", () => {
  it("says so at the top whatever the subject is, and never as markup", async () => {
    for (const subject of [{ kind: "project" }, { kind: "part", ref: "tote" }] as const) {
      const inspector = await mounted({ subject, error: "SyntaxError: <img src=x>" });
      expect(inside(inspector, "#error")?.textContent).toBe("SyntaxError: <img src=x>");
      expect(inside(inspector, "img")).toBeNull();
    }
  });

  it("says nothing of a failure when the run did not fail", async () => {
    const inspector = await mounted();
    expect(inside(inspector, "#error")).toBeNull();
  });
});

describe("bench-inspector, hidden parts", () => {
  it("marks a hidden part's row, and offers show all only while something is hidden", async () => {
    const shown = await mounted();
    expect(inside<HTMLButtonElement>(shown, "#refs-show-all")?.disabled).toBe(true);
    const hidden = await mounted({ hiddenRefs: ["lid"] });
    expect(inside(hidden, '.part[data-part="lid"]')?.dataset["hidden"]).toBe("true");
    expect(caught(hidden, "refs-show-all", () => inside(hidden, "#refs-show-all")?.click())).toHaveLength(1);
  });
});

describe("bench-inspector, a selection by ref (task-92)", () => {
  /** The place row a list marks as lit, across both shadow roots. */
  async function markedPlace(inspector: BenchInspector): Promise<string | undefined> {
    const list = inside(inspector, "#part-findings bench-violation-list");
    await (list as unknown as { updateComplete: Promise<unknown> } | null)?.updateComplete;
    const rows = Array.from(list?.shadowRoot?.querySelectorAll<BenchViolation>("bench-violation") ?? []);
    for (const row of rows) await row.updateComplete;
    return rows
      .map((row) => row.shadowRoot?.querySelector('.place[aria-current="true"]')?.textContent.trim())
      .find((one) => one !== undefined);
  }

  it("shows the part the status bar's count goes to, with the first place of its worst finding marked", async () => {
    // The lid has the error; the tote only a warning.
    const worst = worstPlace(RUN.parts ?? [], RUN.violations ?? []);
    expect(worst).toEqual({ part: "lid", place: "lid/rim" });
    const inspector = await mounted({ subject: { kind: "part", ref: "lid" }, lit: worst?.place ?? null });
    expect(inside(inspector, "#crumb-part")?.textContent.trim()).toBe("lid");
    expect(inside(inspector, "#crumb-part")?.getAttribute("aria-current")).toBe("page");
    expect(await markedPlace(inspector)).toBe("lid/rim");
    expect(inside(inspector, "#selection")?.textContent).toBe("lid/rim");
  });

  it("stays on the part across a run that took its lit place away, the part itself lit", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "tote" }, lit: "tote/lug-1" });
    expect(await markedPlace(inspector)).toBe("tote/lug-1");
    const refs = REFS.filter((ref) => ref !== "tote/lug-1");
    const overhangs = { ...OVERHANGS, refs: ["tote/floor"] };
    const kept = keptAcross({ subject: inspector.subject, lit: inspector.lit }, RUN.parts ?? [], refs);
    await given(inspector, { refs, violations: [overhangs, WALL], ...kept });
    expect(inside(inspector, "#crumb-part")?.getAttribute("aria-current")).toBe("page");
    expect(inside(inspector, "#crumb-part")?.textContent.trim()).toBe("tote");
    expect(inside(inspector, "#selection")?.textContent).toBe("tote");
    expect(await markedPlace(inspector)).toBeUndefined();
  });

  it("goes back to the project across a run that no longer makes the part", async () => {
    const inspector = await mounted({ subject: { kind: "part", ref: "tote" }, lit: "tote" });
    const parts = [LID, PANEL];
    const refs = REFS.filter((ref) => !ref.startsWith("tote"));
    const kept = keptAcross({ subject: inspector.subject, lit: inspector.lit }, parts, refs);
    await given(inspector, { parts, refs, violations: [WALL], ...kept });
    expect(inside(inspector, "#crumb-project")?.getAttribute("aria-current")).toBe("page");
    expect(sections(inspector)).not.toContain("part-findings");
    expect(inside(inspector, '.part[data-part="tote"]')).toBeNull();
  });
});
