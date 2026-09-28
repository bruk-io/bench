import { afterEach, describe, expect, it } from "vitest";

import "./panel";
import type { BenchPanel, PanelTab } from "./panel";

type Fields = Partial<Pick<BenchPanel, "stdout" | "stderr" | "collapsed">>;

async function mounted(fields: Fields = {}): Promise<BenchPanel> {
  const panel = document.createElement("bench-panel");
  Object.assign(panel, fields);
  document.body.append(panel);
  await panel.updateComplete;
  return panel;
}

const inside = <T extends Element = HTMLElement>(panel: BenchPanel, selector: string): T | null =>
  panel.shadowRoot?.querySelector<T>(selector) ?? null;

/** What one tab's little mark says - "" when it says nothing at all. */
const counted = (panel: BenchPanel, tab: PanelTab): string =>
  inside(panel, `#panel-tab-${tab} .count`)?.textContent.trim() ?? "";

const chosen = (panel: BenchPanel): string => inside(panel, '[role="tab"][aria-selected="true"]')?.id ?? "";

async function click(panel: BenchPanel, selector: string): Promise<void> {
  const button = inside(panel, selector);
  if (button === null) throw new Error(`nothing to click at ${selector}`);
  button.click();
  await panel.updateComplete;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-panel, what its tabs say they hold", () => {
  it("says nothing on either tab for a run that said nothing", async () => {
    const panel = await mounted();
    expect(counted(panel, "output")).toBe("");
    expect(counted(panel, "stderr")).toBe("");
  });

  it("marks a stream that said anything with a dot rather than a number", async () => {
    const panel = await mounted({ stdout: "box is 120 mm wide\n", stderr: "  \n" });
    expect(counted(panel, "output")).toBe("•");
    // Whitespace is not something said.
    expect(counted(panel, "stderr")).toBe("");
  });

  it("holds only what the script printed - no findings and no files (decision-12)", async () => {
    const panel = await mounted();
    const tabs = Array.from(panel.shadowRoot?.querySelectorAll('[role="tab"]') ?? [], (tab) => tab.id);
    expect(tabs).toEqual(["panel-tab-output", "panel-tab-stderr"]);
  });
});

describe("bench-panel, the two streams", () => {
  it("keeps them on tabs of their own, so a warning is never lost in the output", async () => {
    const panel = await mounted({ stdout: "printed on stdout\n", stderr: "written on stderr\n", collapsed: false });
    expect(inside(panel, "#stdout")?.textContent).toBe("printed on stdout\n");
    expect(inside(panel, "#stderr")).toBeNull();
    await click(panel, "#panel-tab-stderr");
    expect(inside(panel, "#stderr")?.textContent).toBe("written on stderr\n");
    expect(inside(panel, "#stdout")).toBeNull();
  });

  it("says a stream is empty rather than showing an empty box", async () => {
    const panel = await mounted();
    await click(panel, "#panel-tab-output");
    expect(inside(panel, ".quiet")?.textContent.trim()).toBe("This run printed nothing.");
  });

  it("never turns what it was given into markup", async () => {
    const panel = await mounted({ stdout: "<img src=x>", collapsed: false });
    expect(inside(panel, "img")).toBeNull();
  });
});

describe("bench-panel, being put away", () => {
  it("starts folded, with no tab in front and no body drawn", async () => {
    const panel = await mounted({ stdout: "said\n" });
    expect(panel.collapsed).toBe(true);
    expect(panel.hasAttribute("collapsed")).toBe(true);
    expect(chosen(panel)).toBe("");
    // Its tab still says something waits behind it.
    expect(counted(panel, "output")).toBe("•");
  });

  it("puts itself away when the tab in front is clicked again, and comes back", async () => {
    const panel = await mounted({ collapsed: false });
    await click(panel, "#panel-tab-output");
    expect(panel.collapsed).toBe(true);
    await click(panel, "#panel-tab-output");
    expect(panel.collapsed).toBe(false);
  });

  it("opens itself when the page asks for a tab", async () => {
    const panel = await mounted();
    panel.show("stderr");
    await panel.updateComplete;
    expect(panel.collapsed).toBe(false);
    expect(chosen(panel)).toBe("panel-tab-stderr");
  });
});
