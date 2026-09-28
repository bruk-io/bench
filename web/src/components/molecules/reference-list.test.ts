import { afterEach, describe, expect, it } from "vitest";

import "./reference-list";
import type { BenchReferenceList, ReferencePickDetail } from "./reference-list";

type Fields = Partial<Pick<BenchReferenceList, "references" | "activeReference" | "selectedReference">>;

async function mounted(fields: Fields = {}): Promise<BenchReferenceList> {
  const list = document.createElement("bench-reference-list");
  Object.assign(list, fields);
  document.body.append(list);
  await list.updateComplete;
  return list;
}

/** The rows, by the file each stands for. */
const references = (list: BenchReferenceList): string[] =>
  Array.from(list.shadowRoot?.querySelectorAll<HTMLElement>(".row.reference") ?? []).map(
    (row) => row.dataset["reference"] ?? "",
  );

const referenceRow = (list: BenchReferenceList, file: string): HTMLElement => {
  const row = Array.from(list.shadowRoot?.querySelectorAll<HTMLElement>(".row.reference") ?? []).find(
    (one) => one.dataset["reference"] === file,
  );
  if (row === undefined) {
    throw new Error(`no reference row for ${file}; on screen: ${references(list).join(", ")}`);
  }
  return row;
};

const BRACKET = "bracket.stl";

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-reference-list", () => {
  it("lists every body the project holds, and marks the one that is active", async () => {
    const list = await mounted({ references: [BRACKET, "foot.stl"], activeReference: "foot.stl" });
    expect(references(list)).toEqual([BRACKET, "foot.stl"]);
    expect(referenceRow(list, "foot.stl").dataset["active"]).toBe("true");
    expect(referenceRow(list, "foot.stl").querySelector(".active")?.textContent).toBe("active");
    expect(referenceRow(list, BRACKET).dataset["active"]).toBe("false");
    expect(referenceRow(list, BRACKET).querySelector(".active")).toBeNull();
  });

  it("gives a body one row and nothing under it", async () => {
    // decision-8: an imported mesh names nothing under it. decision-7: no survey indexing.
    const list = await mounted({ references: [BRACKET] });
    const row = referenceRow(list, BRACKET);
    expect(row.getAttribute("aria-expanded")).toBeNull();
    expect(row.children).toHaveLength(1);
  });

  it("draws nothing when the project holds no body", async () => {
    const list = await mounted();
    expect(references(list)).toEqual([]);
  });

  it("sends the file up on a click and never selects itself", async () => {
    const list = await mounted({ references: [BRACKET] });
    const seen: string[] = [];
    list.addEventListener("reference-pick", (event: CustomEvent<ReferencePickDetail>) => {
      seen.push(event.detail.file);
    });
    referenceRow(list, BRACKET).click();
    await list.updateComplete;
    expect(seen).toEqual([BRACKET]);
    // The page owns the selection, exactly as it does for a ref.
    expect(list.selectedReference).toBeNull();
  });

  it("marks the one the page says is selected, and only that one", async () => {
    const list = await mounted({ references: [BRACKET, "foot.stl"], selectedReference: BRACKET });
    expect(referenceRow(list, BRACKET).getAttribute("aria-current")).toBe("true");
    expect(referenceRow(list, "foot.stl").getAttribute("aria-current")).toBe("false");
  });

  it("answers the keyboard the way a ref row does", async () => {
    const list = await mounted({ references: [BRACKET] });
    const seen: string[] = [];
    list.addEventListener("reference-pick", (event: CustomEvent<ReferencePickDetail>) => {
      seen.push(event.detail.file);
    });
    referenceRow(list, BRACKET).dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await list.updateComplete;
    expect(seen).toEqual([BRACKET]);
  });
});
