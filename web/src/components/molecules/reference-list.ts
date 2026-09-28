/** The bodies somebody else made that the open project holds, one row each, with the active one
 * marked.
 *
 * These were a group at the head of the refs tree; decision-12 moved them to the project's
 * inspector, because a reference is not something a run named - it is a thing of the project's,
 * and choosing one makes it the subject whose tools (survey, detect faces, placement) the
 * inspector then shows. A reference is one row with nothing under it: decision-8's imported mesh
 * "names nothing under it the way a hull does", and decision-7 refused pointing at a survey's own
 * indexing, so there is nothing to nest.
 *
 * A click goes up as `reference-pick` and nothing more: the page decides what is active and
 * what is selected, and says so here, the way the refs tree's own round-trip works.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";

import { base } from "../styles";

/** Which dropped body a person picked. */
export interface ReferencePickDetail {
  readonly file: string;
}

@customElement("bench-reference-list")
export class BenchReferenceList extends LitElement {
  static override styles = [
    base,
    css`
      :host {
        display: block;
      }

      .row {
        display: flex;
        align-items: center;
        gap: 6px;
        width: 100%;
        padding: 3px 8px;
        border-radius: 5px;
        color: var(--fg);
        font: 400 11px/1.5 var(--mono);
        cursor: pointer;
        white-space: nowrap;
      }

      .row:hover {
        background: var(--panel-2);
      }

      .row[aria-current="true"] {
        background: color-mix(in srgb, var(--select) 16%, transparent);
        box-shadow: inset 2px 0 0 var(--select);
      }

      .name {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .active {
        flex: none;
        color: var(--accent);
        font-family: var(--sans);
        font-size: 10px;
      }
    `,
  ];

  /** The bodies the project holds, by file name - and the one on the view when it is not one of
   * them (a drop a reader made, or one the host would not take). */
  @property({ attribute: false }) references: readonly string[] = [];

  /** The one of `references` that is active - the body on the view, and the one `survey`,
   * *detect faces* and the pick panel are about (decision-9, task-49). Choosing a row is what
   * makes it so; the page decides, and marks it here. */
  @property({ attribute: false }) activeReference: string | null = null;

  /** Which reference is selected - the inspector's subject - when one is. */
  @property({ attribute: "selected-reference" }) selectedReference: string | null = null;

  override render() {
    return this.references.map(
      (file) => html`
        <div
          class="row reference"
          role="button"
          tabindex="0"
          aria-current=${file === this.selectedReference ? "true" : "false"}
          data-reference=${file}
          data-active=${file === this.activeReference ? "true" : "false"}
          @click=${() => {
            this.pick(file);
          }}
          @keydown=${(event: KeyboardEvent) => {
            this.keyed(event, file);
          }}
        >
          <span class="name">${file}</span>
          ${file === this.activeReference ? html`<span class="active">active</span>` : nothing}
        </div>
      `,
    );
  }

  private keyed(event: KeyboardEvent, file: string): void {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    this.pick(file);
  }

  /** This never selects itself, so the page stays the one owner of what is selected. */
  private pick(file: string): void {
    this.dispatchEvent(
      new CustomEvent<ReferencePickDetail>("reference-pick", { bubbles: true, composed: true, detail: { file } }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-reference-list": BenchReferenceList;
  }

  interface HTMLElementEventMap {
    "reference-pick": CustomEvent<ReferencePickDetail>;
  }
}
