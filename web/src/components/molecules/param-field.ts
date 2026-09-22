/** One parameter as a labelled widget: a number, a switch, a choice or a line of text.
 *
 * The value comes down; an edit goes up as `param-change`, and only once it is a value. A
 * number field is half-typed far more often than it is wrong - clearing "3" to type "5" passes
 * through "", and on a tablet that is the only way to change it - and read as a value that
 * empty string is `0`, which a Gridfinity bin zero units deep turns into an exception. So a
 * field in that state says what it wants under itself and sends nothing. Leaving the field (or
 * Enter) is the person saying "that is the number": an emptied field goes back to what it was,
 * and a number past either end of the range is held at that end.
 *
 * The widget is written to from `value` only when what it holds no longer reads as `value`, so
 * the value an edit sends coming straight back down never rewrites the field under the person
 * typing - "3." stays "3." while 3 goes up and comes back.
 */
import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import { customElement, property, query, state } from "lit/decorators.js";
import { ifDefined } from "lit/directives/if-defined.js";

import type { ParamKind, Scalar } from "../../scene";
import { base } from "../styles";

/** An edit that is a value: which parameter, and what it is now. */
export interface ParamChangeDetail {
  readonly name: string;
  readonly value: Scalar;
}

@customElement("bench-param-field")
export class BenchParamField extends LitElement {
  static override styles = [
    base,
    css`
      :host {
        position: relative;
        display: grid;
        grid-template-columns: minmax(0, 1fr) 92px;
        align-items: center;
        gap: 0 10px;
        min-height: 32px;
        padding: 0 0 0 10px;
        border-radius: 6px;
        font-size: 12px;
      }

      /* An overridden value gets a mark in the margin, so a glance down the panel says which
         numbers are the script's and which are yours. */
      :host::before {
        content: "";
        position: absolute;
        top: 50%;
        left: 0;
        width: 4px;
        height: 4px;
        margin-top: -2px;
        border-radius: 50%;
        background: transparent;
      }

      :host([set])::before {
        background: var(--accent);
      }

      label {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      :host([set]) label {
        font-weight: 600;
      }

      .name {
        margin-left: 6px;
        color: var(--fg-faint);
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 400;
      }

      input,
      select {
        width: 100%;
        height: 26px;
        padding: 0 7px;
        font: inherit;
        font-variant-numeric: tabular-nums;
        color: var(--fg);
        background: var(--panel-2);
        border: 1px solid var(--line);
        border-radius: 6px;
        transition:
          border-color 0.12s,
          background-color 0.12s;
      }

      input:hover,
      select:hover {
        border-color: var(--line-strong);
      }

      input:focus,
      select:focus {
        outline: none;
        background: var(--panel);
        border-color: var(--accent);
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent);
      }

      :host([set]) input:not([type="checkbox"]),
      :host([set]) select {
        border-color: color-mix(in srgb, var(--accent) 45%, var(--line));
      }

      /* Waiting on the person: emptied, or past its range. Not run, and the range it wants
         shows under it, so a tablet user clearing a number sees why nothing moved. */
      .invalid input,
      .invalid input:focus {
        border-color: var(--danger);
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--danger) 18%, transparent);
      }

      .wants {
        grid-column: 2;
        margin-top: -2px;
        font-size: 10px;
        line-height: 1.2;
        text-align: right;
        color: var(--danger);
      }

      /* A checkbox as a switch: the parameter is on or off, and a switch says that. */
      input[type="checkbox"] {
        appearance: none;
        position: relative;
        justify-self: end;
        width: 30px;
        height: 18px;
        margin: 0;
        padding: 0;
        border: none;
        border-radius: 999px;
        background: var(--line-strong);
        cursor: pointer;
      }

      input[type="checkbox"]::after {
        content: "";
        position: absolute;
        top: 2px;
        left: 2px;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #fff;
        box-shadow: 0 1px 2px rgb(0 0 0 / 25%);
        transition: transform 0.15s;
      }

      input[type="checkbox"]:checked {
        background: var(--accent);
      }

      input[type="checkbox"]:checked::after {
        transform: translateX(12px);
      }

      .row {
        display: contents;
      }
    `,
  ];

  /** The parameter's name in the script - what an edit is sent up as. */
  @property() name = "";

  /** What the panel calls it. */
  @property() label = "";

  @property() kind: ParamKind = "float";

  @property({ type: Number }) min: number | null = null;

  @property({ type: Number }) max: number | null = null;

  @property({ type: Number }) step: number | null = null;

  /** What a `choice` may be. */
  @property({ attribute: false }) choices: readonly Scalar[] = [];

  /** The value in force: the override when there is one, the script's default when not. */
  @property({ attribute: false }) value: Scalar = 0;

  /** Whether `value` is an override rather than the script's own. */
  @property({ type: Boolean, reflect: true }) set = false;

  /** What the field is waiting for, while what it holds is not a value. */
  @state() private wants: string | null = null;

  // No initializer: `@query` is a getter on the prototype, and a field assignment would throw
  // against it before the element was ever constructed.
  @query("input, select") private widget!: HTMLInputElement | HTMLSelectElement | null;

  override render() {
    const id = `param-${this.name}`;
    return html`
      <div class="row ${this.wants === null ? "" : "invalid"}">
        <label for=${id}>
          ${this.label}${this.label === this.name
            ? nothing
            : html`<span class="name">${this.name}</span>`}
        </label>
        ${this.control(id)}
        ${this.wants === null ? nothing : html`<span class="wants">${this.wants}</span>`}
      </div>
    `;
  }

  private control(id: string) {
    if (this.kind === "choice") {
      return html`
        <select id=${id} @change=${this.edited}>
          ${this.choices.map(
            (choice) => html`
              <option value=${String(choice)} .selected=${String(choice) === String(this.value)}>
                ${String(choice)}
              </option>
            `,
          )}
        </select>
      `;
    }
    if (this.kind === "bool") {
      return html`
        <input
          id=${id}
          type="checkbox"
          .checked=${this.value === true || this.value === "true"}
          @change=${this.edited}
        />
      `;
    }
    if (this.kind === "str") {
      return html`<input id=${id} type="text" @input=${this.edited} />`;
    }
    return html`
      <input
        id=${id}
        type="number"
        step=${this.step ?? (this.kind === "int" ? 1 : 0.1)}
        min=${ifDefined(this.min ?? undefined)}
        max=${ifDefined(this.max ?? undefined)}
        @input=${this.edited}
        @change=${this.committed}
      />
    `;
  }

  /** A value from outside - a reset, a new example - settles a field that was waiting. */
  override willUpdate(changed: PropertyValues<this>): void {
    if ((changed.has("value") || changed.has("set")) && this.stale()) this.wants = null;
  }

  /** Put `value` into the widget - but only when the widget no longer says it, so an edit's
   * own value coming back down leaves the typing alone. */
  override updated(changed: PropertyValues<this>): void {
    const widget = this.widget;
    if ((changed.has("value") || changed.has("set")) && this.stale() && widget !== null) {
      widget.value = String(this.value);
    }
  }

  /** Whether the text widget holds something other than `value`. */
  private stale(): boolean {
    const widget = this.widget;
    if (!(widget instanceof HTMLInputElement) || widget.type === "checkbox") return false;
    return this.reads(widget) !== this.value;
  }

  /** What the widget holds, as the value it would send - or `null` when it is not one. */
  private reads(widget: HTMLInputElement): Scalar | null {
    if (widget.type === "text") return widget.value;
    if (this.problem(widget) !== null) return null;
    const said = Number(widget.value);
    return this.kind === "int" ? Math.round(said) : said;
  }

  /** What is wrong with a number field as it stands, or `null`. */
  private problem(widget: HTMLInputElement): string | null {
    if (widget.type !== "number") return null;
    const said = Number(widget.value);
    if (widget.value.trim() === "" || !Number.isFinite(said)) return this.range() ?? "a number";
    if (this.min !== null && said < this.min) return this.range();
    if (this.max !== null && said > this.max) return this.range();
    return null;
  }

  /** The declared range in words - "1–5", "at least 0.86" - or `null` when there is none. */
  private range(): string | null {
    if (this.min !== null && this.max !== null) return `${this.min}–${this.max}`;
    if (this.min !== null) return `at least ${this.min}`;
    if (this.max !== null) return `at most ${this.max}`;
    return null;
  }

  private edited(event: Event): void {
    const widget = event.target;
    if (widget instanceof HTMLSelectElement) {
      this.send(widget.value);
      return;
    }
    if (!(widget instanceof HTMLInputElement)) return;
    if (widget.type === "checkbox") {
      this.send(widget.checked);
      return;
    }
    this.wants = this.problem(widget);
    const value = this.reads(widget);
    if (value !== null) this.send(value);
  }

  /** The person is done with the field: settle whatever is still wrong, then send it. An int
   * left holding a fraction is settled too - it already sent the rounded value, and a field
   * that goes on saying `2.5` is showing a number the script never got. */
  private committed(event: Event): void {
    const widget = event.target;
    if (!(widget instanceof HTMLInputElement)) return;
    const fraction = this.kind === "int" && !Number.isInteger(Number(widget.value));
    if (this.problem(widget) === null && !fraction) return;
    const said = Number(widget.value);
    const settled =
      widget.value.trim() === "" || !Number.isFinite(said)
        ? Number(this.value)
        : Math.min(this.max ?? Infinity, Math.max(this.min ?? -Infinity, said));
    widget.value = String(this.kind === "int" ? Math.round(settled) : settled);
    this.edited(event);
  }

  private send(value: Scalar): void {
    this.dispatchEvent(
      new CustomEvent<ParamChangeDetail>("param-change", {
        bubbles: true,
        composed: true,
        detail: { name: this.name, value },
      }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-param-field": BenchParamField;
  }

  interface HTMLElementEventMap {
    "param-change": CustomEvent<ParamChangeDetail>;
  }
}
