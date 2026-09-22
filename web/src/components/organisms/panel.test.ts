import { afterEach, describe, expect, it } from "vitest";

import type { SheetView, ViolationView } from "../../scene";
import type { BenchFileRow } from "../molecules/file-row";
import "./panel";
import type { BenchPanel, FileSaveDetail, FilesSaveAllDetail, PanelTab } from "./panel";

const WALL: ViolationView = {
  check: "wall",
  message: "thinnest wall is 0.6 mm",
  severity: "error",
  refs: ["lid/wall-0"],
  line: 12,
};

const OVERHANG: ViolationView = { ...WALL, check: "overhangs", severity: "warning" };

const SHEET: SheetView = {
  name: "sheet-3mm-01",
  thickness: 3,
  svg: "<svg>from the sheet</svg>",
  preview: "<svg>the sheet, drawn to be seen small</svg>",
  parts: ["front", "back"],
};

/** 2048 zero bytes as base64: 2.0 kB of file, 2.7 kB of string. */
const STL = btoa("\0".repeat(2048));

type Fields = Partial<
  Pick<
    BenchPanel,
    "error" | "violations" | "warnings" | "stdout" | "stderr" | "sheets" | "files" | "collapsed"
  >
>;

async function mounted(fields: Fields = {}): Promise<BenchPanel> {
  const panel = document.createElement("bench-panel");
  Object.assign(panel, fields);
  document.body.append(panel);
  await panel.updateComplete;
  return panel;
}

const inside = <T extends Element = HTMLElement>(panel: BenchPanel, selector: string): T | null =>
  panel.shadowRoot?.querySelector<T>(selector) ?? null;

const rows = (panel: BenchPanel): BenchFileRow[] =>
  Array.from(panel.shadowRoot?.querySelectorAll("bench-file-row") ?? []);

const labels = (row: BenchFileRow | undefined): string[] =>
  Array.from(row?.querySelectorAll("button") ?? [], (button) => button.textContent?.trim() ?? "");

/** What one tab's little count says - "" when it says nothing at all. */
const counted = (panel: BenchPanel, tab: PanelTab): string =>
  inside(panel, `#panel-tab-${tab} .count`)?.textContent?.trim() ?? "";

const chosen = (panel: BenchPanel): string =>
  inside(panel, '[role="tab"][aria-selected="true"]')?.id ?? "";

async function click(panel: BenchPanel, selector: string): Promise<void> {
  const button = inside(panel, selector);
  if (button === null) throw new Error(`nothing to click at ${selector}`);
  button.click();
  await panel.updateComplete;
}

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

describe("bench-panel, what its tabs say they hold", () => {
  it("says nothing on any tab for a run that said nothing", async () => {
    const panel = await mounted();
    expect(counted(panel, "problems")).toBe("");
    expect(counted(panel, "output")).toBe("");
    expect(counted(panel, "stderr")).toBe("");
    expect(counted(panel, "files")).toBe("");
  });

  it("counts the findings, the nest's warnings and a failed run together", async () => {
    const panel = await mounted({
      error: "boom",
      violations: [WALL, OVERHANG],
      warnings: ["part too big for the bed"],
    });
    expect(panel.problems).toBe(4);
    expect(counted(panel, "problems")).toBe("4");
  });

  it("marks a stream that said anything with a dot rather than a number", async () => {
    const panel = await mounted({ stdout: "box is 120 mm wide\n", stderr: "  \n" });
    expect(counted(panel, "output")).toBe("•");
    // Whitespace is not something said.
    expect(counted(panel, "stderr")).toBe("");
  });

  it("counts the files a run made", async () => {
    const panel = await mounted({ files: { "a.svg": "<svg/>", "bin.stl": STL } });
    expect(counted(panel, "files")).toBe("2");
  });
});

describe("bench-panel, the problems tab", () => {
  it("starts in front, and says so when there is nothing wrong", async () => {
    const panel = await mounted();
    expect(chosen(panel)).toBe("panel-tab-problems");
    expect(inside(panel, "#no-problems")).not.toBeNull();
  });

  it("shows a failed run, the findings and the nest's warnings together", async () => {
    const panel = await mounted({
      error: "SyntaxError: invalid syntax",
      violations: [WALL],
      warnings: ["part too big for the bed"],
    });
    expect(inside(panel, "#error")?.textContent).toBe("SyntaxError: invalid syntax");
    expect(inside(panel, "#violations")).not.toBeNull();
    expect(inside(panel, "#warnings li")?.textContent).toBe("part too big for the bed");
  });

  it("never turns what it was given into markup", async () => {
    const panel = await mounted({ error: "<img src=x>", warnings: ["<b>bold</b>"] });
    expect(inside(panel, "img")).toBeNull();
    expect(inside(panel, "b")).toBeNull();
  });
});

describe("bench-panel, the two streams", () => {
  it("keeps them on tabs of their own, so a warning is never lost in the output", async () => {
    const panel = await mounted({ stdout: "printed on stdout\n", stderr: "written on stderr\n" });
    await click(panel, "#panel-tab-output");
    expect(inside(panel, "#stdout")?.textContent).toBe("printed on stdout\n");
    expect(inside(panel, "#stderr")).toBeNull();
    await click(panel, "#panel-tab-stderr");
    expect(inside(panel, "#stderr")?.textContent).toBe("written on stderr\n");
    expect(inside(panel, "#stdout")).toBeNull();
  });

  it("says a stream is empty rather than showing an empty box", async () => {
    const panel = await mounted();
    await click(panel, "#panel-tab-output");
    expect(inside(panel, ".quiet")?.textContent?.trim()).toBe("This run printed nothing.");
  });
});

describe("bench-panel, the files tab", () => {
  it("offers a sheet as SVG, and as DXF only when there is one", async () => {
    const plain = await mounted({ sheets: [SHEET], files: { "sheet-3mm-01.svg": "<svg/>" } });
    await click(plain, "#panel-tab-files");
    expect(labels(rows(plain)[0])).toEqual(["SVG"]);

    const both = await mounted({
      sheets: [SHEET],
      files: { "sheet-3mm-01.svg": "<svg/>", "sheet-3mm-01.dxf": "0\nSECTION" },
    });
    await click(both, "#panel-tab-files");
    expect(labels(rows(both)[0])).toEqual(["SVG", "DXF"]);
  });

  it("describes a sheet by its thickness and the pieces cut from it", async () => {
    const panel = await mounted({ sheets: [SHEET], files: { "sheet-3mm-01.svg": "<svg/>" } });
    await click(panel, "#panel-tab-files");
    expect(rows(panel)[0]?.meta).toBe("3 mm · 2 pieces");
  });

  it("sizes what a printer reads by its bytes rather than its base64", async () => {
    const panel = await mounted({ files: { "bin.stl": STL } });
    await click(panel, "#panel-tab-files");
    expect(rows(panel)[0]?.meta).toBe("2.0 kB");
    expect(labels(rows(panel)[0])).toEqual(["STL"]);
  });

  it("sends a file up rather than saving it", async () => {
    const panel = await mounted({ sheets: [SHEET], files: { "sheet-3mm-01.svg": "<svg>file</svg>" } });
    await click(panel, "#panel-tab-files");
    const detail = caught<FileSaveDetail>("file-save", () => {
      rows(panel)[0]?.querySelector("button")?.click();
    });
    expect(detail).toEqual({ name: "sheet-3mm-01.svg", data: "<svg>file</svg>" });
  });

  it("sends every file up for Download all", async () => {
    const files = { "sheet-3mm-01.svg": "<svg/>", "bin.stl": STL };
    const panel = await mounted({ sheets: [SHEET], files });
    await click(panel, "#panel-tab-files");
    const detail = caught<FilesSaveAllDetail>("files-save-all", () => {
      inside(panel, "#zip")?.click();
    });
    expect(detail).toEqual({ files });
  });

  it("says a run made nothing rather than offering an empty archive", async () => {
    const panel = await mounted();
    await click(panel, "#panel-tab-files");
    expect(inside(panel, "#zip")).toBeNull();
  });
});

describe("bench-panel, being put away", () => {
  it("draws no body while it is collapsed, and its tabs still say what waits", async () => {
    const panel = await mounted({ violations: [WALL], collapsed: true });
    expect(counted(panel, "problems")).toBe("1");
    expect(panel.hasAttribute("collapsed")).toBe(true);
  });

  it("puts itself away when the tab in front is clicked again, and comes back", async () => {
    const panel = await mounted();
    await click(panel, "#panel-tab-problems");
    expect(panel.collapsed).toBe(true);
    await click(panel, "#panel-tab-problems");
    expect(panel.collapsed).toBe(false);
  });

  it("opens itself when the page asks for a tab", async () => {
    const panel = await mounted({ collapsed: true });
    panel.show("files");
    await panel.updateComplete;
    expect(panel.collapsed).toBe(false);
    expect(chosen(panel)).toBe("panel-tab-files");
  });
});
