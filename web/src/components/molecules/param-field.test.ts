import { afterEach, describe, expect, it } from "vitest";

import "./param-field";
import type { BenchParamField, ParamChangeDetail } from "./param-field";

type Fields = Partial<
  Pick<
    BenchParamField,
    "name" | "label" | "kind" | "min" | "max" | "step" | "choices" | "value" | "set"
  >
>;

/** A field for `units_x`, an int from 1 to 7 at 4, unless told otherwise. */
async function mounted(fields: Fields = {}): Promise<BenchParamField> {
  const field = document.createElement("bench-param-field");
  Object.assign(field, { name: "units_x", label: "Units across", kind: "int", min: 1, max: 7, value: 4 }, fields);
  document.body.append(field);
  await field.updateComplete;
  return field;
}

async function given(field: BenchParamField, fields: Fields): Promise<void> {
  Object.assign(field, fields);
  await field.updateComplete;
}

function widget<T extends HTMLElement = HTMLInputElement>(field: BenchParamField): T {
  const found = field.shadowRoot?.querySelector<T>("input, select");
  if (found === null || found === undefined) throw new Error("the field drew no widget");
  return found;
}

/** Everything the field sends up while `act` runs. */
function sent(field: BenchParamField, act: () => void): ParamChangeDetail[] {
  const heard: ParamChangeDetail[] = [];
  const listener = (event: CustomEvent<ParamChangeDetail>): void => {
    heard.push(event.detail);
  };
  field.addEventListener("param-change", listener);
  act();
  field.removeEventListener("param-change", listener);
  return heard;
}

/** Type `text` into the field as a keystroke would leave it. */
function typed(field: BenchParamField, text: string): ParamChangeDetail[] {
  return sent(field, () => {
    const input = widget(field);
    input.value = text;
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  });
}

/** Leave the field, or press Enter in it. */
function committed(field: BenchParamField): ParamChangeDetail[] {
  return sent(field, () => {
    widget(field).dispatchEvent(new Event("change", { bubbles: true }));
  });
}

const wants = (field: BenchParamField): string | null =>
  field.shadowRoot?.querySelector(".wants")?.textContent ?? null;

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-param-field, drawn", () => {
  it("shows a number field at its value, with its range and an int's step", async () => {
    const input = widget(await mounted());
    expect([input.type, input.value, input.min, input.max, input.step]).toEqual([
      "number",
      "4",
      "1",
      "7",
      "1",
    ]);
  });

  it("steps a float by a tenth unless the script says otherwise", async () => {
    expect(widget(await mounted({ kind: "float", value: 3 })).step).toBe("0.1");
    expect(widget(await mounted({ kind: "float", value: 3, step: 0.5 })).step).toBe("0.5");
  });

  it("names the parameter beside its label only when the two differ", async () => {
    const named = await mounted();
    expect(named.shadowRoot?.querySelector(".name")?.textContent).toBe("units_x");
    const plain = await mounted({ label: "units_x" });
    expect(plain.shadowRoot?.querySelector(".name")).toBeNull();
  });

  it("labels its widget, so a click on the label focuses it", async () => {
    const field = await mounted();
    expect(field.shadowRoot?.querySelector("label")?.htmlFor).toBe(widget(field).id);
    expect(widget(field).id).toBe("param-units_x");
  });

  it("reflects whether it is overridden", async () => {
    const field = await mounted({ set: true });
    expect(field.hasAttribute("set")).toBe(true);
  });
});

describe("bench-param-field, laid out", () => {
  it("keeps its widget inside its own column, padding and border included", async () => {
    const field = await mounted();
    field.style.width = "300px";
    await field.updateComplete;
    const input = widget(field).getBoundingClientRect();
    expect(input.width).toBeCloseTo(92, 0);
    expect(input.right).toBeLessThanOrEqual(field.getBoundingClientRect().right + 0.5);
  });
});

describe("bench-param-field, typing a number", () => {
  it("sends a typed number up, rounded for an int", async () => {
    expect(typed(await mounted(), "5.6")).toEqual([{ name: "units_x", value: 6 }]);
  });

  it("sends nothing for an emptied field, and says the range it wants", async () => {
    const field = await mounted();
    expect(typed(field, "")).toEqual([]);
    await field.updateComplete;
    expect(wants(field)).toBe("1–7");
  });

  it("sends nothing past the range", async () => {
    const field = await mounted();
    expect(typed(field, "9")).toEqual([]);
    await field.updateComplete;
    expect(wants(field)).toBe("1–7");
  });

  it("asks for a number when there is no range to name", async () => {
    const field = await mounted({ min: null, max: null });
    typed(field, "");
    await field.updateComplete;
    expect(wants(field)).toBe("a number");
  });

  it("stops asking once what it holds is a value again", async () => {
    const field = await mounted();
    typed(field, "");
    await field.updateComplete;
    typed(field, "3");
    await field.updateComplete;
    expect(wants(field)).toBeNull();
  });
});

describe("bench-param-field, leaving the field", () => {
  it("puts an emptied field back to its value, and sends that", async () => {
    const field = await mounted();
    typed(field, "");
    expect(committed(field)).toEqual([{ name: "units_x", value: 4 }]);
    expect(widget(field).value).toBe("4");
  });

  it("shows an int the whole number it sent, not the fraction typed", async () => {
    const field = await mounted();
    typed(field, "2.5");
    expect(committed(field)).toEqual([{ name: "units_x", value: 3 }]);
    expect(widget(field).value).toBe("3");
  });

  it("leaves a float's fraction as typed", async () => {
    const field = await mounted({ kind: "float", value: 3 });
    typed(field, "2.5");
    expect(committed(field)).toEqual([]);
    expect(widget(field).value).toBe("2.5");
  });

  it("holds a number past the range at the nearer end", async () => {
    const field = await mounted();
    typed(field, "9");
    expect(committed(field)).toEqual([{ name: "units_x", value: 7 }]);
    expect(widget(field).value).toBe("7");
  });
});

describe("bench-param-field, its value coming down", () => {
  it("leaves the typing alone when the edit's own value comes back", async () => {
    const field = await mounted({ kind: "float", value: 2 });
    expect(typed(field, "3.0")).toEqual([{ name: "units_x", value: 3 }]);
    await given(field, { value: 3, set: true });
    expect(widget(field).value).toBe("3.0");
  });

  it("writes a value from outside into the field - a reset", async () => {
    const field = await mounted();
    typed(field, "6");
    await given(field, { value: 6, set: true });
    await given(field, { value: 4, set: false });
    expect(widget(field).value).toBe("4");
  });

  it("settles a field left emptied when it is reset to the value it had", async () => {
    const field = await mounted({ set: true });
    typed(field, "");
    await field.updateComplete;
    await given(field, { set: false });
    expect(widget(field).value).toBe("4");
    expect(wants(field)).toBeNull();
  });
});

describe("bench-param-field, other kinds", () => {
  it("is a switch for a bool, and sends what it was switched to", async () => {
    const field = await mounted({ name: "baseplate", kind: "bool", value: true, min: null, max: null });
    const input = widget(field);
    expect([input.type, input.checked]).toEqual(["checkbox", true]);
    expect(sent(field, () => input.click())).toEqual([{ name: "baseplate", value: false }]);
  });

  it("is a choice for a choice, and follows a reset after a pick", async () => {
    const field = await mounted({ kind: "choice", choices: ["a", "b"], value: "b", min: null, max: null });
    const select = widget<HTMLSelectElement>(field);
    expect(select.value).toBe("b");
    select.value = "a";
    expect(sent(field, () => select.dispatchEvent(new Event("change")))).toEqual([
      { name: "units_x", value: "a" },
    ]);
    await given(field, { value: "a", set: true });
    await given(field, { value: "b", set: false });
    expect(select.value).toBe("b");
  });

  it("is a line of text for a str, sent as typed", async () => {
    const field = await mounted({ name: "labels", kind: "str", value: "x", min: null, max: null });
    expect(widget(field).value).toBe("x");
    expect(typed(field, "a, b")).toEqual([{ name: "labels", value: "a, b" }]);
  });
});
