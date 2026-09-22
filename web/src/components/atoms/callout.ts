/** A block set apart by its tone: something that will not work, something to watch, or
 * something nothing measured.
 *
 * Three tones and three looks, because "I could not measure that" must not read like a pass
 * and "this will not work" must not read like a hint. The content is slotted; the callout
 * only says how loudly it is said.
 */
import { LitElement, css, html } from "lit";
import { customElement, property } from "lit/decorators.js";

import { base } from "../styles";

export type Tone = "danger" | "warn" | "muted";

@customElement("bench-callout")
export class BenchCallout extends LitElement {
  static override styles = [
    base,
    css`
      :host {
        display: block;
        padding: 7px 10px;
        border: 1px solid var(--line);
        border-left-width: 3px;
        border-radius: 6px;
        font-size: 12px;
        color: var(--fg-dim);
        background: var(--panel-2);
      }

      :host([tone="danger"]) {
        color: var(--danger);
        background: var(--danger-soft);
        border-color: color-mix(in srgb, var(--danger) 30%, transparent);
        border-left-color: var(--danger);
      }

      :host([tone="warn"]) {
        color: var(--warn);
        background: var(--warn-soft);
        border-color: color-mix(in srgb, var(--warn) 30%, transparent);
        border-left-color: var(--warn);
      }

      /* Dashed: not a finding at all, only the absence of one. */
      :host([tone="muted"]) {
        border-left-style: dashed;
      }
    `,
  ];

  @property({ reflect: true }) tone: Tone = "muted";

  override render() {
    return html`<slot></slot>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-callout": BenchCallout;
  }
}
