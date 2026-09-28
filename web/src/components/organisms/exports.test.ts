import { afterEach, describe, expect, it } from "vitest";

import type { SheetView } from "../../scene";
import type { BenchFileRow } from "../molecules/file-row";
import "./exports";
import type {
  BenchExports,
  FileSaveDetail,
  FilesSaveAllDetail,
  SheetOpenDetail,
  SlicerOpenDetail,
} from "./exports";

const SHEET: SheetView = {
  name: "sheet-3mm-01",
  thickness: 3,
  svg: "<svg>from the sheet</svg>",
  preview: "<svg>the sheet, drawn to be seen small</svg>",
  parts: ["front", "back"],
};

const ONE_PIECE: SheetView = { ...SHEET, name: "sheet-6mm-01", thickness: 6, parts: ["lid"] };

/** 2048 zero bytes as base64: 2.0 kB of file, 2.7 kB of string. */
const STL = btoa("\0".repeat(2048));

type Fields = Partial<Pick<BenchExports, "sheets" | "files" | "onlyPart" | "slicer" | "opening">>;

async function mounted(fields: Fields = {}): Promise<BenchExports> {
  const list = document.createElement("bench-exports");
  Object.assign(list, fields);
  document.body.append(list);
  await list.updateComplete;
  return list;
}

const inside = <T extends Element = HTMLElement>(list: BenchExports, selector: string): T | null =>
  list.shadowRoot?.querySelector<T>(selector) ?? null;

const rows = (list: BenchExports): BenchFileRow[] =>
  Array.from(list.shadowRoot?.querySelectorAll("bench-file-row") ?? []);

/** What a row's download buttons say - not the sheet's own picture, which opens it. */
const labels = (row: BenchFileRow | undefined): string[] =>
  Array.from(row?.querySelectorAll("button:not(.sheet)") ?? [], (button) => button.textContent.trim());

/** The next `type` event to reach the document, from whatever `act` does. */
function caught<T>(type: "file-save" | "files-save-all", act: () => void): T | null {
  let detail: T | null = null;
  const listener = (event: Event): void => {
    detail = (event as CustomEvent<T>).detail;
  };
  document.addEventListener(type, listener);
  act();
  document.removeEventListener(type, listener);
  return detail;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-exports, the project's files", () => {
  it("offers a sheet as SVG, and as DXF only when there is one", async () => {
    const plain = await mounted({ sheets: [SHEET], files: { "sheet-3mm-01.svg": "<svg/>" } });
    expect(labels(rows(plain)[0])).toEqual(["SVG"]);

    const both = await mounted({
      sheets: [SHEET],
      files: { "sheet-3mm-01.svg": "<svg/>", "sheet-3mm-01.dxf": "0\nSECTION" },
    });
    expect(labels(rows(both)[0])).toEqual(["SVG", "DXF"]);
  });

  it("describes a sheet by its thickness and the pieces cut from it", async () => {
    const list = await mounted({ sheets: [SHEET, ONE_PIECE], files: {} });
    expect(rows(list)[0]?.name).toBe("sheet-3mm-01");
    expect(rows(list)[0]?.meta).toBe("3 mm · 2 pieces");
    expect(rows(list)[1]?.meta).toBe("6 mm · 1 piece");
  });

  it("sizes what a printer reads by its bytes rather than its base64", async () => {
    const list = await mounted({ files: { "bin.stl": STL } });
    expect(rows(list)[0]?.meta).toBe("2.0 kB");
    expect(labels(rows(list)[0])).toEqual(["STL"]);
  });

  it("sends a file up rather than saving it", async () => {
    const list = await mounted({ sheets: [SHEET], files: { "sheet-3mm-01.svg": "<svg>file</svg>" } });
    const detail = caught<FileSaveDetail>("file-save", () => {
      rows(list)[0]?.querySelector<HTMLButtonElement>("button:not(.sheet)")?.click();
    });
    expect(detail).toEqual({ name: "sheet-3mm-01.svg", data: "<svg>file</svg>" });
  });

  it("sends every file up for Download all", async () => {
    const files = { "sheet-3mm-01.svg": "<svg/>", "bin.stl": STL };
    const list = await mounted({ sheets: [SHEET], files });
    const detail = caught<FilesSaveAllDetail>("files-save-all", () => {
      inside(list, "#zip")?.click();
    });
    expect(detail).toEqual({ files });
  });

  it("says a run made nothing rather than offering an empty archive", async () => {
    const list = await mounted();
    expect(inside(list, "#zip")).toBeNull();
    expect(inside(list, ".quiet")?.textContent).toContain("no file to take away");
  });
});

describe("bench-exports, a sheet to look at", () => {
  it("shows the preview drawing, not the hairline cut file", async () => {
    const list = await mounted({ sheets: [SHEET] });
    const src = rows(list)[0]?.querySelector(".sheet img")?.getAttribute("src") ?? "";
    expect(src.startsWith("data:image/svg+xml")).toBe(true);
    expect(decodeURIComponent(src.slice(src.indexOf(",") + 1))).toBe(SHEET.preview);
  });

  it("asks for a sheet to be opened rather than opening one itself", async () => {
    const list = await mounted({ sheets: [SHEET] });
    let picked: string | null = null;
    list.addEventListener("sheet-open", (event) => {
      picked = (event as CustomEvent<SheetOpenDetail>).detail.name;
    });
    rows(list)[0]?.querySelector<HTMLButtonElement>(".sheet")?.click();
    expect(picked).toBe("sheet-3mm-01");
  });
});

describe("bench-exports, one part's files", () => {
  const files = {
    "sheet-3mm-01.svg": "<svg/>",
    "sheet-6mm-01.svg": "<svg/>",
    "part-front.svg": "<svg/>",
    "part-lid.svg": "<svg/>",
    "cabinet.3mf": STL,
  };

  it("lists only the sheets the part is on and its own drawing, with no Download all", async () => {
    const list = await mounted({ sheets: [SHEET, ONE_PIECE], files, onlyPart: { ref: "front", label: "front" } });
    expect(rows(list).map((row) => row.name)).toEqual(["sheet-3mm-01", "part-front.svg"]);
    expect(inside(list, "#zip")).toBeNull();
  });

  it("says so when the part has no file of its own", async () => {
    const list = await mounted({ sheets: [SHEET], files, onlyPart: { ref: "runner", label: "runner" } });
    expect(rows(list)).toHaveLength(0);
    expect(inside(list, ".quiet")?.textContent).toContain("no file of its own");
  });
});

describe("bench-exports, open in slicer (task-86)", () => {
  const files = {
    "sheet-3mm-01.svg": "<svg/>",
    "part-front.svg": "<svg/>",
    "knob.stl": STL,
    "cabinet.3mf": STL,
  };

  /** The rows that offer *Open in slicer*, by name. */
  const offered = (list: BenchExports): string[] =>
    rows(list)
      .filter((row) => row.querySelector(".slicer") !== null)
      .map((row) => row.name);

  it("offers it on every file a printer reads, and only when a host is serving the project", async () => {
    const hosted = await mounted({ sheets: [SHEET], files, slicer: true });
    expect(offered(hosted)).toEqual(["knob.stl", "cabinet.3mf"]);
    const hostless = await mounted({ sheets: [SHEET], files });
    expect(offered(hostless)).toEqual([]);
  });

  it("offers it beside a part's own body", async () => {
    const list = await mounted({ files, onlyPart: { ref: "knob", label: "knob" }, slicer: true });
    expect(offered(list)).toEqual(["knob.stl"]);
  });

  it("sends the file up to be opened rather than opening anything itself", async () => {
    const list = await mounted({ files, slicer: true });
    let detail: SlicerOpenDetail | null = null;
    list.addEventListener("slicer-open", (event) => {
      detail = (event as CustomEvent<SlicerOpenDetail>).detail;
    });
    rows(list)
      .find((row) => row.name === "cabinet.3mf")
      ?.querySelector<HTMLButtonElement>(".slicer")
      ?.click();
    expect(detail).toEqual({ name: "cabinet.3mf", data: STL });
  });

  it("says under the row how it went, and holds the button while it is on its way", async () => {
    const list = await mounted({
      files,
      slicer: true,
      opening: {
        "cabinet.3mf": { state: "opening" },
        "knob.stl": { state: "failed", message: "No slicer was found: BambuStudio is not installed." },
      },
    });
    const said = (name: string): HTMLElement | null => inside(list, `.opening[data-file="${name}"]`);
    expect(said("cabinet.3mf")?.textContent.trim()).toBe("Opening cabinet.3mf in the slicer…");
    expect(said("knob.stl")?.classList.contains("failed")).toBe(true);
    expect(said("knob.stl")?.textContent.trim()).toBe("No slicer was found: BambuStudio is not installed.");
    const button = (name: string): HTMLButtonElement | null | undefined =>
      rows(list)
        .find((row) => row.name === name)
        ?.querySelector<HTMLButtonElement>(".slicer");
    expect(button("cabinet.3mf")?.disabled).toBe(true);
    expect(button("knob.stl")?.disabled).toBe(false);

    list.opening = { "cabinet.3mf": { state: "opened", message: "Opened prints/cabinet.3mf in BambuStudio." } };
    await list.updateComplete;
    expect(said("cabinet.3mf")?.textContent.trim()).toBe("Opened prints/cabinet.3mf in BambuStudio.");
    expect(said("knob.stl")).toBeNull();
  });
});
