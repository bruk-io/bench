import { afterEach, describe, expect, it } from "vitest";

import "./reference-tools";
import type { BenchReferenceTools, PickAssignDetail, PickFieldDetail, PickView, ReferenceToolsView } from "./reference-tools";

const PICK: PickView = {
  frame: "",
  read: "Click a coloured face: what it measures reads here.",
  canOrigin: false,
  canCorner: false,
  canUp: false,
  canWrite: true,
  placed: false,
  canUnplace: true,
  origin: "",
  up: "",
  along: "",
  why: "",
  whyBad: false,
};

const VIEW: ReferenceToolsView = {
  chip: "foot.stl",
  chipTitle: "",
  survey: "ready",
  detecting: false,
  detectWaiting: false,
  pick: null,
  said: "",
};

async function mounted(view: ReferenceToolsView | null): Promise<BenchReferenceTools> {
  const tools = document.createElement("bench-reference-tools");
  tools.view = view;
  document.body.append(tools);
  await tools.updateComplete;
  return tools;
}

const inside = <T extends Element = HTMLElement>(tools: BenchReferenceTools, selector: string): T | null =>
  tools.shadowRoot?.querySelector<T>(selector) ?? null;

function caught<T>(tools: BenchReferenceTools, type: string, act: () => void): T[] {
  const seen: T[] = [];
  const listener = (event: Event): void => {
    seen.push((event as CustomEvent<T>).detail);
  };
  tools.addEventListener(type, listener);
  act();
  tools.removeEventListener(type, listener);
  return seen;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-reference-tools", () => {
  it("draws nothing while there is no body", async () => {
    const tools = await mounted(null);
    expect(tools.shadowRoot?.children).toHaveLength(0);
  });

  it("names the body and says whether it is placed or kept", async () => {
    const tools = await mounted({ ...VIEW, chip: "foot.stl · placed · not kept", chipTitle: "not kept in the project: exists" });
    expect(inside(tools, "#reference-name")?.textContent).toBe("foot.stl · placed · not kept");
    expect(inside(tools, "#reference-name")?.getAttribute("title")).toBe("not kept in the project: exists");
  });

  it("offers the survey once it is measured, and says when there is none", async () => {
    const measuring = await mounted({ ...VIEW, survey: "measuring" });
    expect(inside<HTMLButtonElement>(measuring, "#reference-report")?.disabled).toBe(true);
    expect(inside(measuring, "#reference-report")?.textContent.trim()).toBe("measuring…");
    const none = await mounted({ ...VIEW, survey: "none" });
    expect(inside(none, "#reference-report")?.textContent.trim()).toBe("no survey");
    const ready = await mounted(VIEW);
    expect(caught(ready, "reference-survey", () => inside(ready, "#reference-report")?.click())).toHaveLength(1);
  });

  it("asks for detection and for the body to be taken off, and says when detection is on or on its way", async () => {
    const tools = await mounted(VIEW);
    expect(caught(tools, "reference-detect", () => inside(tools, "#reference-detect")?.click())).toHaveLength(1);
    expect(caught(tools, "reference-remove", () => inside(tools, "#reference-clear")?.click())).toHaveLength(1);
    const waiting = await mounted({ ...VIEW, detecting: true, detectWaiting: true });
    expect(inside(waiting, "#reference-detect")?.textContent.trim()).toBe("detecting…");
    expect(inside(waiting, "#reference-detect")?.getAttribute("aria-pressed")).toBe("true");
  });

  it("shows the pick only while faces are detected", async () => {
    expect(inside(await mounted(VIEW), "#pick")).toBeNull();
    expect(inside(await mounted({ ...VIEW, detecting: true, pick: PICK }), "#pick")).not.toBeNull();
  });

  it("sends a typed field up rather than keeping it, and shows the field the page hands down", async () => {
    const tools = await mounted({ ...VIEW, detecting: true, pick: { ...PICK, up: "+Z" } });
    expect(inside<HTMLInputElement>(tools, "#pick-up")?.value).toBe("+Z");
    const field = inside<HTMLInputElement>(tools, "#pick-along");
    const asked = caught<PickFieldDetail>(tools, "pick-field", () => {
      if (field === null) return;
      field.value = "+X";
      field.dispatchEvent(new InputEvent("input", { bubbles: true }));
    });
    expect(asked).toEqual([{ field: "along", text: "+X" }]);
  });

  it("asks for each assignment by name, and only once something has been picked", async () => {
    const none = await mounted({ ...VIEW, detecting: true, pick: PICK });
    expect(inside<HTMLButtonElement>(none, "#pick-as-origin")?.disabled).toBe(true);
    const picked = await mounted({ ...VIEW, detecting: true, pick: { ...PICK, canOrigin: true, canCorner: true, canUp: true } });
    const asked = caught<PickAssignDetail>(picked, "pick-assign", () => {
      inside(picked, "#pick-as-origin")?.click();
      inside(picked, "#pick-as-corner")?.click();
      inside(picked, "#pick-as-up")?.click();
    });
    expect(asked.map((one) => one.how)).toEqual(["origin", "corner", "up"]);
  });

  it("shuts the fields and offers only clearing while the project already places the body", async () => {
    const tools = await mounted({
      ...VIEW,
      detecting: true,
      pick: { ...PICK, placed: true, canWrite: false, frame: "reading the placed frame", why: "already placed" },
    });
    expect(inside<HTMLInputElement>(tools, "#pick-origin")?.disabled).toBe(true);
    expect(inside<HTMLButtonElement>(tools, "#pick-write")?.disabled).toBe(true);
    expect(inside<HTMLButtonElement>(tools, "#pick-unplace")?.hidden).toBe(false);
    expect(inside(tools, "#pick-frame")?.textContent).toBe("reading the placed frame");
    expect(caught(tools, "pick-unplace", () => inside(tools, "#pick-unplace")?.click())).toHaveLength(1);
  });

  it("says a refusal in the danger tone", async () => {
    const tools = await mounted({ ...VIEW, detecting: true, pick: { ...PICK, why: "all three or none", whyBad: true } });
    expect(inside(tools, "#pick-why")?.classList.contains("is-error")).toBe(true);
    expect(caught(tools, "pick-write", () => inside(tools, "#pick-write")?.click())).toHaveLength(1);
  });
});
