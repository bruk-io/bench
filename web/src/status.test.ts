import { describe, expect, it } from "vitest";

import type { SummaryView } from "./scene";
import { built, failing, found, noBodiesReason, readOnlyWords, roughly } from "./status";

describe("readOnlyWords", () => {
  const desk = { label: "Chrome on a Mac", address: "192.168.1.10", forMs: 300_000, heardAgoMs: 4000 };

  it("says whose the project is, where, for how long, and what a reader can and cannot do", () => {
    const said = readOnlyWords("cabinet", desk, false);
    expect(said.title).toBe("cabinet is open for writing in Chrome on a Mac at 192.168.1.10, so it is read-only here.");
    expect(said.text).toContain("held it for 5 minutes");
    expect(said.text).toContain("last heard from a moment ago");
    expect(said.text).toContain("nothing you change is kept");
    expect(said.chip).toBe("read-only");
    expect(said.badge).toBe("read-only · held elsewhere");
    expect(said.badge).toBe(`${said.chip} · ${said.badgeWhy}`);
  });

  it("asks before taking it over, naming whose it is and what that one loses", () => {
    expect(readOnlyWords("cabinet", desk, false).confirm).toBe(
      "Take cabinet from Chrome on a Mac at 192.168.1.10? From then on it can keep nothing: an edit it " +
        "has not saved yet is refused, and it is told you took it over. Do this when that one is " +
        "somewhere you cannot reach.",
    );
  });

  it("says it was taken over, when it was this tab's", () => {
    expect(readOnlyWords("cabinet", desk, true).title).toBe(
      "Chrome on a Mac at 192.168.1.10 took over writing cabinet. It is read-only here now.",
    );
    expect(readOnlyWords("cabinet", desk, true).badge).toBe("read-only · taken over");
  });

  it("puts a span of time roughly", () => {
    expect(roughly(1200)).toBe("a moment");
    expect(roughly(40_000)).toBe("40 seconds");
    expect(roughly(60 * 60_000)).toBe("60 minutes");
    expect(roughly(3 * 60 * 60_000)).toBe("3 hours");
    expect(roughly(60_000 * 1.2)).toBe("72 seconds");
  });
});

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

describe("built and found", () => {
  it("says a single part without a sheet", () => {
    expect(built(summary())).toBe("1 part");
  });

  it("says parts on sheets, and - apart, for the count beside it - what the checks found", () => {
    const both = summary({ parts: 14, sheets: 7, errors: 1, warnings: 2 });
    expect(built(both)).toBe("14 parts on 7 sheets");
    expect(found(both)).toBe("1 error · 2 warnings");
  });

  it("counts one of each in the singular, and says nothing for nothing found", () => {
    expect(found(summary({ warnings: 1 }))).toBe("1 warning");
    expect(found(summary())).toBe("");
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
