import { describe, expect, it } from "vitest";

import { FIRST_LAYOUT, LAYOUTS, isLayout, layoutOf, nextLayout } from "./layout";

describe("layout", () => {
  it("is Code, Split and View, and a browser that never chose sees Split", () => {
    expect(LAYOUTS).toEqual(["code", "split", "view"]);
    expect(FIRST_LAYOUT).toBe("split");
  });

  it("reads back what was remembered", () => {
    for (const layout of LAYOUTS) expect(layoutOf(layout)).toBe(layout);
  });

  it("reads nothing, or anything it does not know, as the first layout", () => {
    expect(layoutOf(null)).toBe("split");
    expect(layoutOf("")).toBe("split");
    expect(layoutOf("Code")).toBe("split");
    expect(layoutOf("stacked")).toBe("split");
  });

  it("knows a layout from anything else", () => {
    expect(isLayout("view")).toBe(true);
    expect(isLayout("views")).toBe(false);
    expect(isLayout(1)).toBe(false);
    expect(isLayout(null)).toBe(false);
  });

  it("steps Code, Split, View and round again", () => {
    expect(nextLayout("code")).toBe("split");
    expect(nextLayout("split")).toBe("view");
    expect(nextLayout("view")).toBe("code");
  });
});
