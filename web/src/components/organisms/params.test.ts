import { afterEach, describe, expect, it } from "vitest";

import type { ParamView } from "../../scene";
import type { BenchParamField, ParamChangeDetail } from "../molecules/param-field";
import "./params";
import type { BenchParams } from "./params";

const UNITS: ParamView = {
  name: "units_x",
  label: "Units across",
  kind: "int",
  default: 4,
  min: 1,
  max: 7,
  step: null,
  choices: null,
};

const BASEPLATE: ParamView = { ...UNITS, name: "baseplate", label: "Baseplate", kind: "bool", default: true };

type Fields = Partial<Pick<BenchParams, "params" | "overrides">>;

async function mounted(fields: Fields): Promise<BenchParams> {
  const panel = document.createElement("bench-params");
  Object.assign(panel, fields);
  document.body.append(panel);
  await panel.updateComplete;
  return panel;
}

async function given(panel: BenchParams, fields: Fields): Promise<void> {
  Object.assign(panel, fields);
  await panel.updateComplete;
}

const fields = (panel: BenchParams): BenchParamField[] =>
  Array.from(panel.shadowRoot?.querySelectorAll("bench-param-field") ?? []);

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-params", () => {
  it("says nothing before a run has said what the script declares", async () => {
    const panel = await mounted({});
    expect(panel.shadowRoot?.textContent?.trim()).toBe("");
  });

  it("says so when the script declares nothing", async () => {
    const panel = await mounted({ params: [] });
    expect(panel.shadowRoot?.querySelector(".empty")?.textContent).toBe(
      "This script declares no parameters.",
    );
  });

  it("draws one field per declaration, at the override or else the default", async () => {
    const panel = await mounted({ params: [UNITS, BASEPLATE], overrides: { units_x: 6 } });
    const drawn = fields(panel).map((one) => [one.name, one.value, one.set]);
    expect(drawn).toEqual([
      ["units_x", 6, true],
      ["baseplate", true, false],
    ]);
  });

  it("keeps every field when the same declarations come again, so typing is never interrupted", async () => {
    const panel = await mounted({ params: [UNITS, BASEPLATE] });
    const before = fields(panel);
    await given(panel, { params: [{ ...UNITS }, { ...BASEPLATE }], overrides: { units_x: 5 } });
    const after = fields(panel);
    expect(after[0]).toBe(before[0]);
    expect(after[1]).toBe(before[1]);
    expect(after[0]?.value).toBe(5);
  });

  it("draws a new field when a declaration changes kind", async () => {
    const panel = await mounted({ params: [UNITS] });
    const [before] = fields(panel);
    await given(panel, { params: [{ ...UNITS, kind: "float" }] });
    expect(fields(panel)[0]).not.toBe(before);
  });

  it("lets a field's edit out of the panel, for the page to act on", async () => {
    const panel = await mounted({ params: [UNITS] });
    const heard: ParamChangeDetail[] = [];
    const listener = (event: CustomEvent<ParamChangeDetail>): void => {
      heard.push(event.detail);
    };
    document.body.addEventListener("param-change", listener);
    const input = fields(panel)[0]?.shadowRoot?.querySelector("input");
    if (input === null || input === undefined) throw new Error("no input");
    input.value = "3";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    document.body.removeEventListener("param-change", listener);
    expect(heard).toEqual([{ name: "units_x", value: 3 }]);
  });
});
