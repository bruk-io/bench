import { describe, expect, it } from "vitest";

import type { SummaryView } from "./scene";
import { failing, noBodiesReason, tally } from "./status";

const summary = (fields: Partial<SummaryView> = {}): SummaryView => ({
  parts: 1,
  sheets: 0,
  errors: 0,
  warnings: 0,
  error_line: null,
  solid: 1,
  unbuilt: 0,
  ...fields,
});

describe("tally", () => {
  it("says a single part without a sheet", () => {
    expect(tally(summary())).toBe("1 part");
  });

  it("says parts on sheets, and what the checks found", () => {
    expect(tally(summary({ parts: 14, sheets: 7, errors: 1, warnings: 2 }))).toBe(
      "14 parts on 7 sheets · 1 error · 2 warnings",
    );
  });
});

describe("failing", () => {
  it("is an error and nothing less", () => {
    expect(failing(summary({ warnings: 3 }))).toBe(false);
    expect(failing(summary({ errors: 1 }))).toBe(true);
  });
});

describe("noBodiesReason", () => {
  it("says nothing when a body was built or nothing went unbuilt", () => {
    expect(noBodiesReason(summary())).toBe("");
    expect(noBodiesReason(summary({ solid: 1, unbuilt: 1 }))).toBe("");
  });

  it("says how many parts went unbuilt, and why", () => {
    expect(noBodiesReason(summary({ solid: 0, unbuilt: 3 }))).toContain("3 parts");
    expect(noBodiesReason(summary({ solid: 0, unbuilt: 1 }))).toContain("built no body");
  });
});
