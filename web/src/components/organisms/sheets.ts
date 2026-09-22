/** The sheets a run nested, as the sidebar's own container.
 *
 * A nested sheet is a drawing a maker reads before they cut, and until now the only place one
 * was ever seen was a thumbnail in a download menu. Each row here opens that sheet as a tab in
 * the centre, where it is big enough to read; the thumbnail stays, as the way to tell one
 * sheet from another at a glance.
 */
import { LitElement, css, html } from "lit";
import { customElement, property } from "lit/decorators.js";

import { pictured } from "../../exports";
import type { SheetView } from "../../scene";
import { base, buttons } from "../styles";

/** Which sheet a person asked to look at. */
export interface SheetOpenDetail {
  readonly name: string;
}

const plural = (count: number, one: string): string => (count === 1 ? one : `${one}s`);

@customElement("bench-sheets")
export class BenchSheets extends LitElement {
  static override styles = [
    base,
    buttons,
    css`
      :host {
        display: block;
        overflow: auto;
        padding: 4px 0;
      }

      .sheet {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        height: auto;
        padding: 5px 8px;
        background: none;
        border: none;
        border-radius: 0;
        box-shadow: none;
        text-align: left;
      }

      .sheet:hover:not(:disabled) {
        background: var(--panel-2);
        border-color: transparent;
      }

      img {
        flex: none;
        width: 44px;
        height: 30px;
        object-fit: contain;
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 3px;
      }

      .about {
        display: grid;
        gap: 1px;
        min-width: 0;
      }

      .name {
        font-family: var(--mono);
        font-size: 11px;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .meta {
        font-size: 10.5px;
        font-weight: 400;
        color: var(--fg-faint);
      }

      .empty {
        margin: 0;
        padding: 4px 10px;
        font-size: 12px;
        color: var(--fg-dim);
      }
    `,
  ];

  /** The sheets the parts were nested onto. */
  @property({ attribute: false }) sheets: readonly SheetView[] = [];

  override render() {
    if (this.sheets.length === 0) {
      return html`<p class="empty">This run nested nothing: there is no flat part to cut.</p>`;
    }
    return this.sheets.map(
      (sheet) => html`
        <button class="sheet" type="button" @click=${() => this.open(sheet.name)}>
          <img alt="" src=${pictured(sheet.preview)} />
          <span class="about">
            <span class="name">${sheet.name}</span>
            <span class="meta">
              ${sheet.thickness} mm · ${sheet.parts.length} ${plural(sheet.parts.length, "piece")}
            </span>
          </span>
        </button>
      `,
    );
  }

  private open(name: string): void {
    this.dispatchEvent(
      new CustomEvent<SheetOpenDetail>("sheet-open", {
        bubbles: true,
        composed: true,
        detail: { name },
      }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-sheets": BenchSheets;
  }

  interface HTMLElementEventMap {
    "sheet-open": CustomEvent<SheetOpenDetail>;
  }
}
