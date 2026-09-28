import { describe, expect, it } from "vitest";

import { layout, partLayout } from "./exports";
import type { SheetView } from "./scene";

const sheet = (name: string, parts: readonly string[]): SheetView => ({
  name,
  thickness: 3,
  svg: "<svg/>",
  preview: "<svg/>",
  parts,
});

const SHEETS = [sheet("sheet-3mm-01", ["side", "side", "back"]), sheet("sheet-3mm-02", ["front"])];

const FILES = {
  "sheet-3mm-01.svg": "<svg/>",
  "sheet-3mm-01.dxf": "0\nEOF",
  "sheet-3mm-02.svg": "<svg/>",
  "part-side.svg": "<svg/>",
  "part-front.svg": "<svg/>",
  "knob.stl": "AAAA",
  "cabinet.3mf": "AAAA",
  "baseplate.scad": "cube(1);",
};

const names = (rows: readonly { name: string }[]): string[] => rows.map((row) => row.name);

describe("layout", () => {
  it("lists every sheet, then what a printer reads, then everything else", () => {
    const all = layout(SHEETS, FILES);
    expect(names(all.sheets)).toEqual(["sheet-3mm-01", "sheet-3mm-02"]);
    expect(names(all.printed)).toEqual(["knob.stl", "cabinet.3mf"]);
    expect(names(all.others)).toEqual(["part-side.svg", "part-front.svg", "baseplate.scad"]);
  });
});

describe("partLayout", () => {
  it("gives a cut part the sheets it is on and its own drawing, and nothing of another part's", () => {
    const side = partLayout({ ref: "side", label: "side" }, SHEETS, FILES);
    expect(names(side.sheets)).toEqual(["sheet-3mm-01"]);
    expect(side.sheets[0]?.downloads.map((one) => one.name)).toEqual(["sheet-3mm-01.svg", "sheet-3mm-01.dxf"]);
    expect(names(side.printed)).toEqual([]);
    expect(names(side.others)).toEqual(["part-side.svg"]);
  });

  it("gives a printed part its own body and leaves the 3MF, which holds every body, to Export all", () => {
    const knob = partLayout({ ref: "knob", label: "knob" }, SHEETS, FILES);
    expect(names(knob.sheets)).toEqual([]);
    expect(names(knob.printed)).toEqual(["knob.stl"]);
    expect(names(knob.others)).toEqual([]);
  });

  it("is empty for a part a run made no file of", () => {
    const none = partLayout({ ref: "runner", label: "runner" }, SHEETS, FILES);
    expect([...none.sheets, ...none.printed, ...none.others]).toEqual([]);
  });
});
