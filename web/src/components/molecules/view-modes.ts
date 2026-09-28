/** The view's way of looking: *Assembled*, *On bed* or *Section* (decision-12's view modes).
 *
 * One of three, always one: a segmented control, a `radiogroup` of three buttons, first in the
 * view's bar because it decides what everything else in the bar is about - the section's axis
 * and position only mean anything in *Section*.
 *
 * It holds no state of its own: the page says which mode is on and hears `view-mode` when a
 * person picks another, and says so back - the same round trip the refs tree and the reference
 * list make, so a re-run or a reload can put the mode back without this being asked.
 */
import { LitElement, css, html } from "lit";
import { customElement, property } from "lit/decorators.js";

import type { ViewMode } from "../../viewer3d";
import { base } from "../styles";

/** The three modes, in the order they are offered, with the words and the tip each wears. */
const MODES: readonly { readonly mode: ViewMode; readonly words: string; readonly tip: string }[] = [
  { mode: "assembled", words: "Assembled", tip: "The parts where the script puts them" },
  { mode: "bed", words: "On bed", tip: "Each printed part the way it prints, on the printer's bed" },
  { mode: "section", words: "Section", tip: "Cut everything at a plane, to see what a part hides inside it" },
];

@customElement("bench-view-modes")
export class BenchViewModes extends LitElement {
  static override styles = [
    base,
    css`
      :host {
        display: inline-flex;
        flex: none;
      }

      .modes {
        display: inline-flex;
        padding: 2px;
        gap: 2px;
        border-radius: 999px;
        background: var(--line);
      }

      button {
        height: 20px;
        padding: 0 9px;
        border: none;
        border-radius: 999px;
        background: none;
        color: var(--fg-dim);
        font: 600 10.5px/1 var(--sans);
        cursor: pointer;
        white-space: nowrap;
      }

      button:hover {
        color: var(--fg);
      }

      button[aria-checked="true"] {
        background: var(--panel);
        color: var(--accent);
        box-shadow: var(--shadow);
      }

      button:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 1px;
      }
    `,
  ];

  /** The mode on now - the page's to say. */
  @property() mode: ViewMode = "assembled";

  override render() {
    return html`<div class="modes" role="radiogroup" aria-label="How to look at the model">
      ${MODES.map(
        (one) => html`<button
          type="button"
          role="radio"
          id=${`mode-${one.mode}`}
          data-mode=${one.mode}
          title=${one.tip}
          aria-checked=${one.mode === this.mode ? "true" : "false"}
          tabindex=${one.mode === this.mode ? "0" : "-1"}
          @click=${() => {
            this.pick(one.mode);
          }}
          @keydown=${(event: KeyboardEvent) => {
            this.keyed(event, one.mode);
          }}
        >
          ${one.words}
        </button>`,
      )}
    </div>`;
  }

  /** A radio group's own keys: the arrows move to the next mode and pick it. */
  private keyed(event: KeyboardEvent, from: ViewMode): void {
    const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const at = MODES.findIndex((one) => one.mode === from);
    const next = MODES[(at + step + MODES.length) % MODES.length];
    if (next === undefined) return;
    this.pick(next.mode);
    void this.updateComplete.then(() => {
      this.shadowRoot?.querySelector<HTMLButtonElement>(`[data-mode="${next.mode}"]`)?.focus();
    });
  }

  /** This never changes its own mode, so the page stays the one owner of it. */
  private pick(mode: ViewMode): void {
    if (mode === this.mode) return;
    this.dispatchEvent(new CustomEvent<ViewMode>("view-mode", { bubbles: true, composed: true, detail: mode }));
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-view-modes": BenchViewModes;
  }

  interface HTMLElementEventMap {
    "view-mode": CustomEvent<ViewMode>;
  }
}
