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

  it("names where to look as a list of places, then the line", async () => {
    const [row] = rows(await mounted([WALL]));
    const places = Array.from(row?.shadowRoot?.querySelectorAll(".places .place") ?? [], (one) =>
      one.textContent.trim(),
    );
    expect(places).toEqual(["lid/wall-0", "lid/wall-1"]);
    expect(row && text(row, ".where .jump")).toBe("line 12");
  });

  it("asks for a place to be lit rather than lighting it, and marks the one the page lit", async () => {
    const list = await mounted([WALL]);
    const [row] = rows(list);
    const asked: string[] = [];
    list.addEventListener("place-pick", (event) => asked.push(event.detail.ref));
    row?.shadowRoot?.querySelector<HTMLButtonElement>('.place[data-ref="lid/wall-1"]')?.click();
    expect(asked).toEqual(["lid/wall-1"]);
    expect(row?.shadowRoot?.querySelector('.place[aria-current="true"]')).toBeNull();
    list.lit = "lid/wall-1";
    await list.updateComplete;
    await row?.updateComplete;
    expect(row?.shadowRoot?.querySelector('.place[aria-current="true"]')?.textContent.trim()).toBe("lid/wall-1");
  });

  it("keeps a long sentence to its first lines until it is clicked", async () => {
    const [row] = rows(await mounted([WALL]));
    const message = row?.shadowRoot?.querySelector<HTMLElement>(".message");
    expect(message?.dataset["open"]).toBe("false");
    message?.click();
    await row?.updateComplete;
    expect(message?.dataset["open"]).toBe("true");
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
