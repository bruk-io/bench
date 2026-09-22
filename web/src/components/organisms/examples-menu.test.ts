import { afterEach, describe, expect, it } from "vitest";

import "./examples-menu";
import type { BenchExamplesMenu, ExamplePickDetail } from "./examples-menu";

const NAMES = ["box_with_hole.py", "gridfinity_bin.py", "hinge.py"];

async function mounted(): Promise<BenchExamplesMenu> {
  const menu = document.createElement("bench-examples-menu");
  menu.names = NAMES;
  document.body.append(menu);
  await menu.updateComplete;
  return menu;
}

const inside = <T extends Element = HTMLElement>(menu: BenchExamplesMenu, selector: string): T | null =>
  menu.shadowRoot?.querySelector<T>(selector) ?? null;

const choices = (menu: BenchExamplesMenu): HTMLButtonElement[] =>
  Array.from(menu.shadowRoot?.querySelectorAll<HTMLButtonElement>("#examples button") ?? []);

const isOpen = (menu: BenchExamplesMenu): boolean =>
  inside(menu, "#examples-button")?.getAttribute("aria-expanded") === "true" &&
  inside(menu, "#examples")?.hidden === false;

async function toggle(menu: BenchExamplesMenu): Promise<void> {
  inside(menu, "#examples-button")?.click();
  await menu.updateComplete;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-examples-menu", () => {
  it("lists the names in the order it was given them, and starts shut", async () => {
    const menu = await mounted();
    expect(choices(menu).map((one) => one.textContent?.trim())).toEqual(NAMES);
    expect(isOpen(menu)).toBe(false);
  });

  it("opens and shuts on its button", async () => {
    const menu = await mounted();
    await toggle(menu);
    expect(isOpen(menu)).toBe(true);
    await toggle(menu);
    expect(isOpen(menu)).toBe(false);
  });

  it("sends the pick up, rather than loading anything, and shuts", async () => {
    const menu = await mounted();
    await toggle(menu);
    let picked: ExamplePickDetail | null = null;
    document.body.addEventListener(
      "example-pick",
      (event) => {
        picked = event.detail;
      },
      { once: true },
    );
    choices(menu)[1]?.click();
    await menu.updateComplete;
    expect(picked).toEqual({ name: "gridfinity_bin.py" });
    expect(isOpen(menu)).toBe(false);
  });

  it("shuts on a click outside it", async () => {
    const menu = await mounted();
    await toggle(menu);
    document.body.click();
    await menu.updateComplete;
    expect(isOpen(menu)).toBe(false);
  });
});
