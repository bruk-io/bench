import { afterEach, describe, expect, it } from "vitest";

import type { ViolationView } from "../../scene";
import "./violation-list";
import type { BenchViolation } from "./violation";
import type { BenchViolationList } from "./violation-list";

const WALL: ViolationView = {
  check: "wall",
  message: "thinnest wall is 0.6 mm",
  severity: "error",
  refs: ["lid/wall-0", "lid/wall-1"],
  line: 12,
};

const FITS: ViolationView = {
  check: "fits",
  message: "no kernel to measure with",
  severity: "unchecked",
  refs: [],
  line: null,
};

async function mounted(violations: readonly ViolationView[]): Promise<BenchViolationList> {
  const list = document.createElement("bench-violation-list");
  list.violations = violations;
  document.body.append(list);
  await list.updateComplete;
  await Promise.all(rows(list).map((row) => row.updateComplete));
  return list;
}

const rows = (list: BenchViolationList): BenchViolation[] =>
  Array.from(list.shadowRoot?.querySelectorAll("bench-violation") ?? []);

const text = (row: BenchViolation, selector: string): string =>
  row.shadowRoot?.querySelector(selector)?.textContent?.trim() ?? "";

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-violation-list", () => {
  it("renders one row per violation, in order", async () => {
    const list = await mounted([WALL, FITS]);
    expect(rows(list).map((row) => row.check)).toEqual(["wall", "fits"]);
  });

  it("renders nothing for no violations", async () => {
    const list = await mounted([]);
    expect(rows(list)).toHaveLength(0);
  });

  it("re-renders when handed new violations", async () => {
    const list = await mounted([WALL, FITS]);
    list.violations = [FITS];
    await list.updateComplete;
    expect(rows(list).map((row) => row.check)).toEqual(["fits"]);
  });
});

describe("bench-violation", () => {
  it("reflects its severity and check onto the host", async () => {
    const [row] = rows(await mounted([WALL]));
    expect(row?.getAttribute("severity")).toBe("error");
    expect(row?.getAttribute("check")).toBe("wall");
  });

  it("names where to look: the refs, then the line", async () => {
    const [row] = rows(await mounted([WALL]));
    expect(row && text(row, ".where")).toBe("lid/wall-0 · lid/wall-1 · line 12");
  });

  it("leaves out where to look when there is nowhere", async () => {
    const [row] = rows(await mounted([FITS]));
    expect(row?.shadowRoot?.querySelector(".where")).toBeNull();
  });

  it("says 'not checked' for unchecked, never the word unchecked", async () => {
    const [row] = rows(await mounted([FITS]));
    expect(row && text(row, ".head")).toBe("not checked");
  });

  it("uses the danger tone for an error and the muted one for unchecked", async () => {
    const [error, unchecked] = rows(await mounted([WALL, FITS]));
    const tone = (row: BenchViolation | undefined): string | null =>
      row?.shadowRoot?.querySelector("bench-callout")?.getAttribute("tone") ?? null;
    expect(tone(error)).toBe("danger");
    expect(tone(unchecked)).toBe("muted");
  });

  it("shows a message as text, never as markup", async () => {
    const [row] = rows(await mounted([{ ...WALL, message: "<img src=x onerror=alert(1)>" }]));
    expect(row?.shadowRoot?.querySelector("img")).toBeNull();
    expect(row && text(row, ".message")).toBe("<img src=x onerror=alert(1)>");
  });
});
