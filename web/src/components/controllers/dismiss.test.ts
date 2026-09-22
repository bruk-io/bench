import { LitElement, html } from "lit";
import { customElement } from "lit/decorators.js";
import { afterEach, describe, expect, it } from "vitest";

import { DismissController } from "./dismiss";

/** The smallest host there is: it counts how often it was told to shut. */
@customElement("test-dismissable")
class TestDismissable extends LitElement {
  dismissed = 0;

  constructor() {
    super();
    new DismissController(this, () => {
      this.dismissed += 1;
    });
  }

  override render() {
    return html`<button type="button">inside</button>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "test-dismissable": TestDismissable;
  }
}

async function mounted(): Promise<TestDismissable> {
  const host = document.createElement("test-dismissable");
  document.body.append(host);
  await host.updateComplete;
  return host;
}

const key = (name: string, cancelable = false): KeyboardEvent =>
  new KeyboardEvent("keydown", { key: name, bubbles: true, cancelable });

afterEach(() => {
  document.body.replaceChildren();
});

describe("DismissController", () => {
  it("dismisses on a click outside the host", async () => {
    const host = await mounted();
    document.body.click();
    expect(host.dismissed).toBe(1);
  });

  it("leaves a click inside the host's own shadow root alone", async () => {
    const host = await mounted();
    host.shadowRoot?.querySelector("button")?.click();
    expect(host.dismissed).toBe(0);
  });

  it("dismisses on Escape and on no other key", async () => {
    const host = await mounted();
    document.body.dispatchEvent(key("Enter"));
    expect(host.dismissed).toBe(0);
    document.body.dispatchEvent(key("Escape"));
    expect(host.dismissed).toBe(1);
  });

  it("leaves an Escape that something nearer the keyboard already handled", async () => {
    const host = await mounted();
    window.addEventListener("keydown", (event) => event.preventDefault(), {
      capture: true,
      once: true,
    });
    document.body.dispatchEvent(key("Escape", true));
    expect(host.dismissed).toBe(0);
  });

  it("stops listening once the host is disconnected, and starts again when it is back", async () => {
    const host = await mounted();
    host.remove();
    document.body.click();
    document.body.dispatchEvent(key("Escape"));
    expect(host.dismissed).toBe(0);
    document.body.append(host);
    document.body.click();
    expect(host.dismissed).toBe(1);
  });
});
