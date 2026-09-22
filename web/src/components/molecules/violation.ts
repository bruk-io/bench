/** One thing a check found, as a row: how much it matters, what it says, and where to look.
 *
 * Everything comes in as its own attribute or property rather than as one `ViolationView`
 * object, so the row can be written by hand in markup and its severity and check are on the
 * host for anything that needs to find one.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";

import type { Severity } from "../../scene";
import "../atoms/callout";
import type { Tone } from "../atoms/callout";
import { base } from "../styles";

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
        grid-template-columns: auto 1fr;
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

      .where {
        grid-column: 2;
        font-family: var(--mono);
        font-size: 10.5px;
        opacity: 0.8;
      }

      /* The line that asked for the check is a way back to it, not a number to read out. */
      .jump {
        padding: 0;
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

  /** The refs the finding is about. */
  @property({ attribute: false }) refs: readonly string[] = [];

  /** The line of the script that asked for the check, when there is one. */
  @property({ type: Number }) line: number | null = null;

  override render() {
    const named = this.refs.join(" · ");
    const line = this.line;
    if (named === "" && line === null) return this.callout(nothing);
    // One expression with no whitespace between its parts: a newline in the template is a
    // newline in `textContent`, and this line is read as one string - "lid/wall-0 · line 12".
    const separator = named !== "" && line !== null ? " · " : "";
    const jump =
      line === null
        ? nothing
        : html`<button class="jump" type="button" @click=${this.jump}>line ${line}</button>`;
    return this.callout(html`<span class="where">${named}${separator}${jump}</span>`);
  }

  private callout(where: unknown) {
    return html`
      <bench-callout tone=${TONE[this.severity]}>
        <div class="row">
          <span class="head" part="head">${HEADING[this.severity]}</span>
          <span class="message">${this.message}</span>
          ${where}
        </div>
      </bench-callout>
    `;
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
  }

  /** It bubbles out of the panel's shadow root and is listened for on the document, which
   * has an event map of its own. */
  interface DocumentEventMap {
    "goto-line": CustomEvent<GotoLineDetail>;
  }
}
