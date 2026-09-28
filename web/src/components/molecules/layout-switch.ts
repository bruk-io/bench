/** Code | Split | View: how the centre is shared between the script and the view (task-91).
 *
 * Three buttons as one control, the one in use pressed. The layout comes down; a pick goes up
 * as `layout-pick`, and laying the centre out - and remembering it - is the page's to do, as it
 * is for the shortcut that steps through the same three.
 */
import { LitElement, css, html } from "lit";
import { customElement, property } from "lit/decorators.js";

import { LAYOUTS, LAYOUT_NAMES, type Layout } from "../../layout";
import { base, buttons } from "../styles";

/** Which layout a person picked. */
export interface LayoutPickDetail {
  readonly layout: Layout;
}

/** What each button says it does, beyond its name. */
const PURPOSE: Readonly<Record<Layout, string>> = {
  code: "The script across the whole centre, for writing",
  split: "The script and the view side by side",
  view: "The view across the whole centre, for checking and printing",
};

@customElement("bench-layout-switch")
export class BenchLayoutSwitch extends LitElement {
  static override styles = [
    base,
    buttons,
    css`
      :host {
        display: inline-flex;
        flex: none;
      }

      .switch {
        display: inline-flex;
        padding: 2px;
        gap: 2px;
        border-radius: 999px;
        background: var(--panel-2);
      }

      button {
        height: 22px;
        padding: 0 10px;
        font-size: 11px;
        font-weight: 600;
        border: none;
        border-radius: 999px;
        background: none;
        box-shadow: none;
        color: var(--fg-dim);
      }

      button:hover:not(:disabled) {
        background: var(--line);
        border-color: transparent;
        color: var(--fg);
      }

      button[aria-pressed="true"],
      button[aria-pressed="true"]:hover:not(:disabled) {
        background: var(--panel);
        color: var(--fg);
        box-shadow: var(--shadow);
      }
    `,
  ];

  /** The layout the centre is in. */
  @property() layout: Layout = "split";

  /** The shortcut that steps through the layouts, as the page binds it - said on every button. */
  @property() shortcut = "";

  override render() {
    const also = this.shortcut === "" ? "" : ` (${this.shortcut} for the next)`;
    return html`
      <div class="switch" role="group" aria-label="Layout">
        ${LAYOUTS.map(
          (layout) => html`
            <button
              id=${`layout-${layout}`}
              type="button"
              aria-pressed=${layout === this.layout ? "true" : "false"}
              title=${`${PURPOSE[layout]}${also}`}
              @click=${() => this.pick(layout)}
            >
              ${LAYOUT_NAMES[layout]}
            </button>
          `,
        )}
      </div>
    `;
  }

  private pick(layout: Layout): void {
    this.dispatchEvent(
      new CustomEvent<LayoutPickDetail>("layout-pick", { bubbles: true, composed: true, detail: { layout } }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-layout-switch": BenchLayoutSwitch;
  }

  interface HTMLElementEventMap {
    "layout-pick": CustomEvent<LayoutPickDetail>;
  }
}
