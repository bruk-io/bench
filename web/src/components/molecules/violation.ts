/** One thing a check found, as a row: how much it matters, what it says, and where to look.
 *
 * Everything comes in as its own attribute or property rather than as one `ViolationView`
 * object, so the row can be written by hand in markup and its severity and check are on the
 * host for anything that needs to find one.
 *
 * Where to look is a list of places, one per ref, each a button (decision-12): since task-78 a
 * check names every place it found - the tote's overhangs are eighteen - and a sentence naming
 * five of them is a wall of text, where a list is somewhere to go. A click on a place goes up as
 * `place-pick` and nothing more; the page lights it in the view and says back which one is lit
 * as `lit`, the same round-trip the refs tree makes.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type { Severity } from "../../scene";
import "../atoms/callout";
import type { Tone } from "../atoms/callout";
import { base } from "../styles";

/** Which place of a finding a person asked to see. */
export interface PlacePickDetail {
  readonly ref: string;
}

/** Which line of the script a person asked to be taken to. */
export interface GotoLineDetail {
  readonly line: number;
}

const TONE: Readonly<Record<Severity, Tone>> = {
  error: "danger",
  warning: "warn",
  unchecked: "muted",
};

/** "not checked" rather than the word `unchecked`, which a maker reads as a pass with a
 * prefix. Nothing measured it; that is a different thing from nothing being wrong. */
const HEADING: Readonly<Record<Severity, string>> = {
  error: "error",
  warning: "warning",
  unchecked: "not checked",
};

@customElement("bench-violation")
export class BenchViolation extends LitElement {
  static override styles = [
    base,
    css`
      :host {
        display: block;
      }

      .row {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: 3px 10px;
        align-items: baseline;
      }

      .head {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        white-space: nowrap;
      }

      /* A long sentence - "18 places lean further off the build direction than..." - is kept
         to three lines until it is clicked: the places under it say the same thing as a list. */
      .message {
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 3;
        overflow: hidden;
        cursor: pointer;
      }

      .message[data-open="true"] {
        display: block;
      }

      .where {
        grid-column: 1 / -1;
        display: grid;
        gap: 2px;
        min-width: 0;
        font-family: var(--mono);
        font-size: 10.5px;
      }

      .places {
        display: grid;
        gap: 1px;
        min-width: 0;
        margin: 2px 0 0;
        padding: 0;
        list-style: none;
      }

      .place {
        display: block;
        width: 100%;
        padding: 1px 5px;
        border: none;
        border-radius: 4px;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        cursor: pointer;
      }

      .place:hover {
        background: color-mix(in srgb, currentcolor 10%, transparent);
      }

      .place[aria-current="true"] {
        background: color-mix(in srgb, var(--select) 18%, transparent);
        box-shadow: inset 2px 0 0 var(--select);
        color: var(--fg);
      }

      /* The line that asked for the check is a way back to it, not a number to read out. */
      .jump {
        justify-self: start;
        padding: 0 5px;
        border: none;
        background: none;
        color: inherit;
        font: inherit;
        text-decoration: underline;
        text-underline-offset: 2px;
        cursor: pointer;
      }

      .jump:hover {
        text-decoration-thickness: 2px;
      }
    `,
  ];

  @property({ reflect: true }) severity: Severity = "unchecked";

  /** Which check found it - `wall`, `fits` - named so a person or a test can pick one out. */
  @property({ reflect: true }) check = "";

  @property() message = "";

  /** The refs the finding is about - its places. */
  @property({ attribute: false }) refs: readonly string[] = [];

  /** The line of the script that asked for the check, when there is one. */
  @property({ type: Number }) line: number | null = null;

  /** The place the view has lit, when it is one of these - the page's, drawn here. */
  @property() lit: string | null = null;

  /** Whether the whole sentence is showing rather than its first three lines. */
  @state() private open = false;

  override render() {
    const line = this.line;
    if (this.refs.length === 0 && line === null) return this.callout(nothing);
    const places =
      this.refs.length === 0
        ? nothing
        : html`<ul class="places">
            ${this.refs.map(
              (ref) =>
                html`<li>
                  <button
                    class="place"
                    type="button"
                    data-ref=${ref}
                    aria-current=${ref === this.lit ? "true" : "false"}
                    title="Light this place in the view"
                    @click=${() => {
                      this.pickPlace(ref);
                    }}
                  >${ref}</button>
                </li>`,
            )}
          </ul>`;
    const jump =
      line === null
        ? nothing
        : html`<button class="jump" type="button" @click=${this.jump}>line ${line}</button>`;
    return this.callout(html`<div class="where">${places}${jump}</div>`);
  }

  private callout(where: unknown) {
    return html`
      <bench-callout tone=${TONE[this.severity]}>
        <div class="row">
          <span class="head" part="head">${HEADING[this.severity]}</span>
          <span class="message" data-open=${String(this.open)} @click=${this.toggle}>${this.message}</span>
          ${where}
        </div>
      </bench-callout>
    `;
  }

  private toggle(): void {
    this.open = !this.open;
  }

  /** Ask for a place to be lit; the page is what lights it. */
  private pickPlace(ref: string): void {
    this.dispatchEvent(
      new CustomEvent<PlacePickDetail>("place-pick", { bubbles: true, composed: true, detail: { ref } }),
    );
  }

  /** Ask for the line that asked for this check; the page is what moves the cursor. */
  private jump(): void {
    if (this.line === null) return;
    this.dispatchEvent(
      new CustomEvent<GotoLineDetail>("goto-line", {
        bubbles: true,
        composed: true,
        detail: { line: this.line },
      }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-violation": BenchViolation;
  }

  interface HTMLElementEventMap {
    "goto-line": CustomEvent<GotoLineDetail>;
    "place-pick": CustomEvent<PlacePickDetail>;
  }

  /** It bubbles out of the panel's shadow root and is listened for on the document, which
   * has an event map of its own. */
  interface DocumentEventMap {
    "goto-line": CustomEvent<GotoLineDetail>;
  }
}
