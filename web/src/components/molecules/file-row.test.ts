import { afterEach, describe, expect, it } from "vitest";

import "./file-row";
import type { BenchFileRow } from "./file-row";

/** A row as a sheet's is drawn in the inspector: a picture, two buttons, in a column `width`
 * pixels across - 280 is the inspector, 244 the narrow window's. */
async function mounted(stacked: boolean, width: number): Promise<BenchFileRow> {
  const column = document.createElement("div");
  column.style.width = `${String(width)}px`;
  const row = document.createElement("bench-file-row");
  Object.assign(row, { name: "sheet-3mm-01", meta: "3 mm · 16 pieces", stacked });
  row.innerHTML = `<button slot="preview" style="width: 48px; height: 32px">·</button><button>SVG</button><button>DXF</button>`;
  column.append(row);
  document.body.append(column);
  await row.updateComplete;
  return row;
}

const part = (row: BenchFileRow, selector: string): HTMLElement => {
  const found = row.shadowRoot?.querySelector<HTMLElement>(selector);
  if (found == null) throw new Error(`no ${selector} in the row`);
  return found;
};

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-file-row", () => {
  it("says the name and the note beside it", async () => {
    const row = await mounted(false, 400);
    expect(part(row, ".name").textContent).toBe("sheet-3mm-01");
    expect(part(row, ".meta").textContent).toBe("3 mm · 16 pieces");
    expect(row.hasAttribute("stacked")).toBe(false);
    expect(part(row, ".meta").getBoundingClientRect().top).toBe(part(row, ".name").getBoundingClientRect().top);
  });

  for (const width of [280, 244]) {
    it(`stacked, keeps a sheet's whole name in a column ${String(width)} px across, its note under it (task-94)`, async () => {
      const row = await mounted(true, width);
      expect(row.hasAttribute("stacked")).toBe(true);
      const name = part(row, ".name");
      expect(name.scrollWidth).toBeLessThanOrEqual(name.clientWidth);
      expect(part(row, ".meta").getBoundingClientRect().top).toBeGreaterThan(name.getBoundingClientRect().top);
    });
  }
});
