/** What can be done with a reference mesh - a body somebody else made, on the view - shown only
 * while that body is the inspector's subject (decision-12).
 *
 * Its survey, *detect faces*, taking it off the view, and decision-7's pick: while faces are
 * being detected, a click on a coloured face reads here, and three fields become the project's
 * `[reference]` placement in one act. These used to float over the view whether or not a body
 * was in play; they are the body's tools, so they sit with the body.
 *
 * A view, nothing more. What it shows comes down as one `ReferenceToolsView` - worked out by the
 * page, which holds the body, the detection and the picks (`reference-body.ts`) - and every
 * click and keystroke goes back up as an event. Even the fields' text is the page's: a pick can
 * write into a field as well as a person can, and one owner is what keeps the two from fighting.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";
import { live } from "lit/directives/live.js";

import { base, buttons } from "../styles";

/** The pick panel, as the page's own state makes it. */
export interface PickView {
  /** Which frame the numbers are in, said only when it is not the exported one. */
  readonly frame: string;
  /** What the last click measured, or how to make one. */
  readonly read: string;
  readonly canOrigin: boolean;
  readonly canCorner: boolean;
  readonly canUp: boolean;
  readonly canWrite: boolean;
  /** Whether the open project already places this body - the fields are then shut and the way
   * out is to clear the placement. */
  readonly placed: boolean;
  readonly canUnplace: boolean;
  readonly origin: string;
  readonly up: string;
  readonly along: string;
  /** A refusal, or what a pick resolved to. */
  readonly why: string;
  readonly whyBad: boolean;
}

/** Everything the tools show about the body on the view. */
export interface ReferenceToolsView {
  /** The file, and `placed` or `not kept` when either is true. */
  readonly chip: string;
  readonly chipTitle: string;
  readonly survey: "measuring" | "ready" | "none";
  readonly detecting: boolean;
  /** Waiting on the worker's detection. */
  readonly detectWaiting: boolean;
  /** The pick panel - `null` while faces are not being detected, the one mode in which a click on
   * the body means anything. */
  readonly pick: PickView | null;
  /** What choosing another reference did to `[reference]`, when it did more than name it. */
  readonly said: string;
}

/** Which of the pick's assignments a person asked for. */
export interface PickAssignDetail {
  readonly how: "origin" | "corner" | "up";
}

/** A pick field typed into. */
export interface PickFieldDetail {
  readonly field: "origin" | "up" | "along";
  readonly text: string;
}

type Plain = "reference-survey" | "reference-detect" | "reference-remove" | "pick-write" | "pick-unplace";

const SURVEY: Readonly<Record<ReferenceToolsView["survey"], string>> = {
  measuring: "measuring…",
  ready: "survey",
  none: "no survey",
};

@customElement("bench-reference-tools")
export class BenchReferenceTools extends LitElement {
  static override styles = [
    base,
    buttons,
    css`
      :host {
        display: grid;
        gap: 8px;
      }

      .name {
        margin: 0;
        font-family: var(--mono);
        font-size: 11px;
        color: var(--fg);
        overflow-wrap: anywhere;
      }

      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
      }

      .actions button[aria-pressed="true"] {
        background: var(--accent-soft);
        border-color: color-mix(in srgb, var(--accent) 40%, transparent);
        color: var(--accent);
      }

      .said {
        margin: 0;
        font-size: 11px;
        color: var(--fg-dim);
      }

      .pick {
        display: grid;
        grid-template-columns: max-content minmax(0, 1fr);
        gap: 4px 6px;
        align-items: center;
        padding: 8px;
        border: 1px solid var(--line);
        border-radius: var(--radius);
        background: var(--panel-2);
      }

      .pick-line {
        grid-column: 1 / -1;
        display: flex;
        align-items: center;
        gap: 5px;
        flex-wrap: wrap;
      }

      .pick-title {
        font-size: 11px;
        font-weight: 600;
      }

      .pick-frame {
        font-size: 10.5px;
        color: var(--accent);
      }

      .pick-read {
        grid-column: 1 / -1;
        margin: 0;
        font-family: var(--mono);
        font-size: 10.5px;
        line-height: 1.45;
        color: var(--fg-dim);
        white-space: pre-line;
        overflow-wrap: anywhere;
      }

      .pick-field {
        font-size: 11px;
        color: var(--fg-dim);
      }

      .pick-value {
        min-width: 0;
        width: 100%;
        height: 22px;
        padding: 0 6px;
        font-family: var(--mono);
        font-size: 10.5px;
        color: var(--fg);
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 5px;
      }

      .pick button {
        height: 22px;
        padding: 0 7px;
        font-size: 10.5px;
        font-weight: 600;
      }

      .pick .pick-quiet {
        font-weight: 500;
        color: var(--fg-dim);
      }

      .pick-why {
        grid-column: 1 / -1;
        margin: 0;
        font-size: 10.5px;
        line-height: 1.4;
        color: var(--fg-dim);
      }

      .pick-why:empty {
        display: none;
      }

      .pick-why.is-error {
        color: var(--danger);
      }
    `,
  ];

  @property({ attribute: false }) view: ReferenceToolsView | null = null;

  override render() {
    const view = this.view;
    if (view === null) return nothing;
    return html`
      <p id="reference-name" class="name" title=${view.chipTitle}>${view.chip}</p>
      <div class="actions">
        <button
          id="reference-report"
          type="button"
          class="small"
          title="Read what the body measures"
          ?disabled=${view.survey !== "ready"}
          @click=${() => {
            this.plain("reference-survey");
          }}
        >
          ${SURVEY[view.survey]}
        </button>
        <button
          id="reference-detect"
          type="button"
          class="small"
          title="Colour the body's detected faces, and click one to see what it is"
          aria-pressed=${view.detecting ? "true" : "false"}
          ?disabled=${view.detectWaiting}
          @click=${() => {
            this.plain("reference-detect");
          }}
        >
          ${view.detectWaiting ? "detecting…" : "detect faces"}
        </button>
        <button
          id="reference-clear"
          type="button"
          class="small ghost"
          title="Take this body off the view - a mesh in the project stays there"
          @click=${() => {
            this.plain("reference-remove");
          }}
        >
          take off the view
        </button>
      </div>
      ${view.said === "" ? nothing : html`<p id="references-said" class="said" role="status">${view.said}</p>`}
      ${view.pick === null ? nothing : this.pickPanel(view.pick)}
    `;
  }

  private pickPanel(pick: PickView) {
    return html`
      <section id="pick" class="pick" aria-label="Place this body">
        <div class="pick-line">
          <span class="pick-title">place this body</span>
          <span id="pick-frame" class="pick-frame">${pick.frame}</span>
        </div>
        <p id="pick-read" class="pick-read">${pick.read}</p>
        <div class="pick-line">
          <button
            id="pick-as-origin"
            type="button"
            title="Write the point the ray met into origin"
            ?disabled=${!pick.canOrigin}
            @click=${() => {
              this.assign("origin");
            }}
          >
            origin = hit
          </button>
          <button
            id="pick-as-corner"
            type="button"
            title="Write the nearest corner of the face into origin - the one a named word can be"
            ?disabled=${!pick.canCorner}
            @click=${() => {
              this.assign("corner");
            }}
          >
            origin = corner
          </button>
          <button
            id="pick-as-up"
            type="button"
            title="Write this face's own normal into up"
            ?disabled=${!pick.canUp}
            @click=${() => {
              this.assign("up");
            }}
          >
            up = this face
          </button>
        </div>
        ${this.field("origin", pick.origin, "low, high, centre or x, y, z", pick.placed)}
        ${this.field("up", pick.up, "+Z or x, y, z", pick.placed)}
        ${/* Typed, and deliberately so: decision-7 designs no edge-pick, and this builds none. */ ""}
        ${this.field("along", pick.along, "+X or x, y, z (typed)", pick.placed)}
        <div class="pick-line">
          <button
            id="pick-write"
            type="button"
            title="Write these three numbers into the project's [reference] table"
            ?disabled=${!pick.canWrite}
            @click=${() => {
              this.plain("pick-write");
            }}
          >
            write [reference]
          </button>
          <button
            id="pick-unplace"
            type="button"
            class="pick-quiet"
            title="Forget this project's placement, so a pick reads the body as exported again"
            ?hidden=${!pick.placed}
            ?disabled=${!pick.canUnplace}
            @click=${() => {
              this.plain("pick-unplace");
            }}
          >
            clear placement
          </button>
        </div>
        <p id="pick-why" class="pick-why ${pick.whyBad ? "is-error" : ""}">${pick.why}</p>
      </section>
    `;
  }

  private field(field: PickFieldDetail["field"], value: string, hint: string, shut: boolean) {
    return html`
      <label class="pick-field" for=${`pick-${field}`}>${field}</label>
      <input
        id=${`pick-${field}`}
        class="pick-value"
        type="text"
        spellcheck="false"
        placeholder=${hint}
        .value=${live(value)}
        ?disabled=${shut}
        @input=${(event: InputEvent) => {
          this.typed(field, (event.target as HTMLInputElement).value);
        }}
      />
    `;
  }

  private plain(type: Plain): void {
    this.dispatchEvent(new CustomEvent(type, { bubbles: true, composed: true }));
  }

  private assign(how: PickAssignDetail["how"]): void {
    this.dispatchEvent(
      new CustomEvent<PickAssignDetail>("pick-assign", { bubbles: true, composed: true, detail: { how } }),
    );
  }

  private typed(field: PickFieldDetail["field"], text: string): void {
    this.dispatchEvent(
      new CustomEvent<PickFieldDetail>("pick-field", { bubbles: true, composed: true, detail: { field, text } }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-reference-tools": BenchReferenceTools;
  }

  interface HTMLElementEventMap {
    "reference-survey": CustomEvent<undefined>;
    "reference-detect": CustomEvent<undefined>;
    "reference-remove": CustomEvent<undefined>;
    "pick-write": CustomEvent<undefined>;
    "pick-unplace": CustomEvent<undefined>;
    "pick-assign": CustomEvent<PickAssignDetail>;
    "pick-field": CustomEvent<PickFieldDetail>;
  }
}
