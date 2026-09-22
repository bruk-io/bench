import { afterEach, describe, expect, it } from "vitest";

import type { SheetView } from "../../scene";
import "./sheets";
import type { BenchSheets, SheetOpenDetail } from "./sheets";

const SHEET: SheetView = {
  name: "sheet-3mm-01",
  thickness: 3,
  svg: "<svg>the cut file</svg>",
  preview: "<svg>the sheet, drawn to be seen small</svg>",
  parts: ["front", "back"],
};

const ONE_PIECE: SheetView = { ...SHEET, name: "sheet-6mm-01", thickness: 6, parts: ["lid"] };

async function mounted(sheets: readonly SheetView[]): Promise<BenchSheets> {
  const list = document.createElement("bench-sheets");
  list.sheets = sheets;
  document.body.append(list);
  await list.updateComplete;
  return list;
}

const rows = (list: BenchSheets): HTMLButtonElement[] =>
  Array.from(list.shadowRoot?.querySelectorAll<HTMLButtonElement>(".sheet") ?? []);

const text = (row: HTMLButtonElement | undefined, selector: string): string =>
  row?.querySelector(selector)?.textContent?.trim() ?? "";

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-sheets", () => {
  it("says a run nested nothing rather than drawing an empty list", async () => {
    const list = await mounted([]);
    expect(rows(list)).toHaveLength(0);
    expect(list.shadowRoot?.querySelector(".empty")?.textContent).toContain("nested nothing");
  });

  it("names each sheet by its thickness and the pieces cut from it", async () => {
    const list = await mounted([SHEET, ONE_PIECE]);
    expect(text(rows(list)[0], ".name")).toBe("sheet-3mm-01");
    expect(text(rows(list)[0], ".meta")).toBe("3 mm · 2 pieces");
    expect(text(rows(list)[1], ".meta")).toBe("6 mm · 1 piece");
  });

  it("shows the preview drawing, not the hairline cut file", async () => {
    const list = await mounted([SHEET]);
    const src = rows(list)[0]?.querySelector("img")?.getAttribute("src") ?? "";
    expect(src.startsWith("data:image/svg+xml")).toBe(true);
    expect(decodeURIComponent(src.slice(src.indexOf(",") + 1))).toBe(SHEET.preview);
  });

  it("asks for a sheet to be opened rather than opening one itself", async () => {
    const list = await mounted([SHEET]);
    let picked: string | null = null;
    list.addEventListener("sheet-open", (event) => {
      picked = (event as CustomEvent<SheetOpenDetail>).detail.name;
    });
    rows(list)[0]?.click();
    expect(picked).toBe("sheet-3mm-01");
  });
});
