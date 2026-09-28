/** The open project is being written somewhere else (task-47): a chip in the header saying so,
 * and a popover with the rest (task-91).
 *
 * It was a notice over the editor that took a third of its height for as long as the project
 * was read here - every word of which is still here, one click away: whose it is and where,
 * for how long and when that one was last heard from, what a reader can do and what is not
 * kept, and the one way to make it yours without waiting. Take over is asked twice, because it
 * takes the project from somebody, and is in the page, never a browser dialog.
 *
 * The words come down, already written (`status.ts`'s `readOnlyWords`); the take-over goes up
 * as `lease-take-over`, and asking the host for it is the page's. Whether the popover is open,
 * and whether it is asking, are this element's own, so a renewal - new words every few seconds
 * - never shuts it under the cursor. When this tab was the writer and somebody took it over,
 * the popover opens by itself: that is news, and a chip alone would not tell it.
 */
import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type { ReadOnlyWords } from "../../status";
import { DismissController } from "../controllers/dismiss";
import { base, buttons, disclosure } from "../styles";

@customElement("bench-lease-chip")
export class BenchLeaseChip extends LitElement {
  static override styles = [
    base,
    buttons,
    disclosure,
    css`
      :host {
        position: relative;
        display: inline-flex;
        flex: none;
      }

      #lease-badge {
        height: 20px;
        padding: 0 8px;
        gap: 4px;
        font-size: 11px;
        font-weight: 600;
        border: none;
        border-radius: 999px;
        box-shadow: none;
        background: var(--warn-soft);
        color: var(--warn);
      }

      #lease-badge:hover:not(:disabled) {
        background: var(--warn-soft);
        border-color: transparent;
        filter: brightness(0.96);
      }

      :host([lost]) #lease-badge {
        background: var(--danger-soft);
        color: var(--danger);
      }

      /* A narrow header has room for the one word; the popover still says all of it. */
      @media (max-width: 760px) {
        .why {
          display: none;
        }
      }

      .pop {
        position: absolute;
        top: calc(100% + 8px);
        left: 0;
        z-index: 20;
        width: min(380px, calc(100vw - 24px));
        padding: 12px;
        background: var(--panel);
        color: var(--fg);
        border: 1px solid var(--line-strong);
        border-radius: 10px;
        box-shadow: var(--shadow-pop);
        font-size: 12px;
        line-height: 1.45;
        white-space: normal;
      }

      /* Above every rule that sets a display: the asking row and the question swap by it. */
      .pop [hidden],
      .pop[hidden] {
        display: none !important;
      }

      p {
        margin: 0 0 8px;
      }

      .title {
        font-weight: 600;
      }

      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin: 0;
      }

      .confirm {
        margin-top: 4px;
        padding-top: 10px;
        border-top: 1px solid var(--line);
      }

      .said {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip-path: inset(50%);
        white-space: nowrap;
      }
    `,
  ];

  /** What to say, or `null` while this tab may write the open project - and then nothing shows. */
  @property({ attribute: false }) words: ReadOnlyWords | null = null;

  /** Whether this tab was the writer and somebody took the project over. */
  @property({ type: Boolean, reflect: true }) lost = false;

  @state() private open = false;

  @state() private confirming = false;

  constructor() {
    super();
    new DismissController(this, () => this.shut());
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("words")) {
      this.hidden = this.words === null;
      if (this.words === null) {
        this.open = false;
        this.confirming = false;
      }
    }
    // Losing the project is the one change nobody asked to be told about: say it unasked.
    if (changed.has("lost") && this.lost && changed.get("lost") !== true) this.open = true;
  }

  override render() {
    const words = this.words;
    if (words === null) return nothing;
    return html`
      <button
        id="lease-badge"
        class="disclosure"
        type="button"
        aria-haspopup="dialog"
        aria-expanded=${this.open ? "true" : "false"}
        aria-controls="lease-pop"
        title=${words.title}
        @click=${this.toggle}
      >
        <span>${words.chip}<span class="why"> · ${words.badgeWhy}</span></span>
      </button>
      <span class="said" role="status">${words.title}</span>
      <div id="lease-pop" class="pop" role="dialog" aria-labelledby="lease-title" ?hidden=${!this.open}>
        <p id="lease-title" class="title">${words.title}</p>
        <p id="lease-why">${words.text}</p>
        <p id="lease-ask" class="actions" ?hidden=${this.confirming}>
          <button id="lease-take" type="button" @click=${this.ask}>Take over writing…</button>
        </p>
        <div id="lease-confirm" class="confirm" ?hidden=${!this.confirming}>
          <p id="lease-confirm-text">${words.confirm}</p>
          <p class="actions">
            <button id="lease-take-yes" type="button" class="primary" @click=${this.takeOver}>Take it over</button>
            <button id="lease-take-no" type="button" @click=${this.leave}>Leave it with them</button>
          </p>
        </div>
      </div>
    `;
  }

  private toggle(): void {
    if (this.open) this.shut();
    else this.open = true;
  }

  private shut(): void {
    this.open = false;
    this.confirming = false;
  }

  private ask(): void {
    this.confirming = true;
  }

  private leave(): void {
    this.confirming = false;
  }

  private takeOver(): void {
    this.shut();
    this.dispatchEvent(new CustomEvent("lease-take-over", { bubbles: true, composed: true }));
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-lease-chip": BenchLeaseChip;
  }

  interface HTMLElementEventMap {
    "lease-take-over": CustomEvent<undefined>;
  }
}
