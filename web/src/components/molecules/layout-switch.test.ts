import { afterEach, describe, expect, it } from "vitest";

import "./layout-switch";
import type { Layout } from "../../layout";
import type { BenchLayoutSwitch, LayoutPickDetail } from "./layout-switch";

async function mounted(layout: Layout = "split"): Promise<BenchLayoutSwitch> {
  const control = document.createElement("bench-layout-switch");
  control.layout = layout;
  control.shortcut = "Ctrl+\\";
  document.body.append(control);
  await control.updateComplete;
  return control;
}

const button = (control: BenchLayoutSwitch, layout: Layout): HTMLButtonElement | null =>
  control.shadowRoot?.querySelector<HTMLButtonElement>(`#layout-${layout}`) ?? null;

const pressed = (control: BenchLayoutSwitch): string[] =>
  Array.from(control.shadowRoot?.querySelectorAll<HTMLButtonElement>('button[aria-pressed="true"]') ?? [], (one) =>
    (one.textContent ?? "").trim(),
  );

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-layout-switch", () => {
  it("offers Code, Split and View, in that order, with the one in use pressed", async () => {
    const control = await mounted("view");
    const names = Array.from(control.shadowRoot?.querySelectorAll("button") ?? [], (one) =>
      (one.textContent ?? "").trim(),
    );
    expect(names).toEqual(["Code", "Split", "View"]);
    expect(pressed(control)).toEqual(["View"]);
  });

  it("follows the layout it is given", async () => {
    const control = await mounted("split");
    control.layout = "code";
    await control.updateComplete;
    expect(pressed(control)).toEqual(["Code"]);
  });

  it("sends a pick up rather than changing itself", async () => {
    const control = await mounted("split");
    let picked: LayoutPickDetail | null = null;
    document.body.addEventListener(
      "layout-pick",
      (event) => {
        picked = event.detail;
      },
      { once: true },
    );
    button(control, "code")?.click();
    await control.updateComplete;
    expect(picked).toEqual({ layout: "code" });
    expect(pressed(control)).toEqual(["Split"]);
  });

  it("names the shortcut on every button", async () => {
    const control = await mounted();
    for (const layout of ["code", "split", "view"] as const) {
      expect(button(control, layout)?.title).toContain("Ctrl+\\");
    }
  });
});
