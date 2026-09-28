import { afterEach, describe, expect, it } from "vitest";

import type { ViewMode } from "../../viewer3d";
import "./view-modes";
import type { BenchViewModes } from "./view-modes";

async function mounted(mode: ViewMode = "assembled"): Promise<BenchViewModes> {
  const modes = document.createElement("bench-view-modes");
  modes.mode = mode;
  document.body.append(modes);
  await modes.updateComplete;
  return modes;
}

const button = (modes: BenchViewModes, mode: ViewMode): HTMLButtonElement => {
  const found = modes.shadowRoot?.querySelector<HTMLButtonElement>(`[data-mode="${mode}"]`);
  if (found === null || found === undefined) throw new Error(`no ${mode} button`);
  return found;
};

/** Every `view-mode` the control sends, in order. */
function heard(modes: BenchViewModes): ViewMode[] {
  const seen: ViewMode[] = [];
  modes.addEventListener("view-mode", (event: CustomEvent<ViewMode>) => {
    seen.push(event.detail);
  });
  return seen;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-view-modes", () => {
  it("offers the three ways of looking, in order, as one radio group", async () => {
    const modes = await mounted();
    const group = modes.shadowRoot?.querySelector('[role="radiogroup"]');
    const offered = Array.from(group?.querySelectorAll<HTMLButtonElement>('[role="radio"]') ?? []);
    expect(offered.map((one) => one.textContent.trim())).toEqual(["Assembled", "On bed", "Section"]);
    expect(offered.map((one) => one.id)).toEqual(["mode-assembled", "mode-bed", "mode-section"]);
  });

  it("marks the mode the page says is on, and only that one", async () => {
    const modes = await mounted("bed");
    expect(button(modes, "bed").getAttribute("aria-checked")).toBe("true");
    expect(button(modes, "assembled").getAttribute("aria-checked")).toBe("false");
    expect(button(modes, "section").getAttribute("aria-checked")).toBe("false");
    modes.mode = "section";
    await modes.updateComplete;
    expect(button(modes, "section").getAttribute("aria-checked")).toBe("true");
    expect(button(modes, "bed").getAttribute("aria-checked")).toBe("false");
  });

  it("sends the mode picked up and never changes its own", async () => {
    const modes = await mounted();
    const seen = heard(modes);
    button(modes, "section").click();
    await modes.updateComplete;
    expect(seen).toEqual(["section"]);
    expect(modes.mode).toBe("assembled");
    expect(button(modes, "assembled").getAttribute("aria-checked")).toBe("true");
  });

  it("says nothing when the mode already on is picked again", async () => {
    const modes = await mounted("bed");
    const seen = heard(modes);
    button(modes, "bed").click();
    expect(seen).toEqual([]);
  });

  it("moves with the arrow keys, round from the last to the first", async () => {
    const modes = await mounted("section");
    const seen = heard(modes);
    button(modes, "section").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    button(modes, "section").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    expect(seen).toEqual(["assembled", "bed"]);
  });

  it("puts only the mode on in the tab order", async () => {
    const modes = await mounted("bed");
    expect(button(modes, "bed").tabIndex).toBe(0);
    expect(button(modes, "assembled").tabIndex).toBe(-1);
    expect(button(modes, "section").tabIndex).toBe(-1);
  });
});
