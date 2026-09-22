/** One file a run made, as a row: a picture of it when there is one, its name, a quiet note on
 * what it is, and the buttons that take it away - the picture and the buttons slotted, so
 * whoever lists the files decides what they show and what a click does. */
import { LitElement, css, html } from "lit";
import { customElement, property } from "lit/decorators.js";

import { base } from "../styles";

@customElement("bench-file-row")
export class BenchFileRow extends LitElement {
  static override styles = [
    base,
    css`
      :host {
        display: flex;
        align-items: center;
        gap: 6px;
        min-height: 32px;
        margin: 0 -6px;
        padding: 0 4px 0 6px;
        border-radius: 6px;
      }

      :host(:hover) {
        background: var(--panel-2);
      }

      .name {
        flex: 1;
        min-width: 0;
        font-family: var(--mono);
        font-size: 11px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .meta {
        margin-right: 4px;
        color: var(--fg-faint);
        font-size: 11px;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
      }
    `,
  ];

  /** The file, or the sheet, as a person would look for it. */
  @property() name = "";

  /** "3 mm · 4 pieces", "12.4 kB". */
  @property() meta = "";

  override render() {
    return html`
      <slot name="preview"></slot>
      <span class="name">${this.name}</span>
      <span class="meta">${this.meta}</span>
      <slot></slot>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-file-row": BenchFileRow;
  }
}
