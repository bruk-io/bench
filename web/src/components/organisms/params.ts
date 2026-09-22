/** The parameters panel, generated from what the script declares.
 *
 * The declarations and the override table both come down; an edit goes up from the field
 * that made it, as `param-change`, and this panel neither keeps a copy of the table nor
 * decides when to run. Fields are keyed by their declaration - name, kind and choices - so a
 * scene that declares the same parameters again keeps every live widget where it is, and
 * typing into a field never has the field pulled out from under the person typing.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";
import { repeat } from "lit/directives/repeat.js";

import type { Overrides } from "../../overrides";
import type { ParamView } from "../../scene";
import "../molecules/param-field";
import { base } from "../styles";

/** What makes a field the same field: a changed kind or choice list is a different widget. */
const identity = (param: ParamView): string =>
  `${param.name}:${param.kind}:${param.choices?.join("|") ?? ""}`;

@customElement("bench-params")
export class BenchParams extends LitElement {
  static override styles = [
    base,
    css`
      /* One column, always: the panel lives in the sidebar now, which is about 240 px wide.
         That is the narrowest home it has had, and it is what giving every surface a home of
         its own costs here - so the fields are laid out for the column rather than left to
         spill out of it. */
      :host {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 2px;
      }

      .empty {
        margin: 0;
        font-size: 12px;
        color: var(--fg-dim);
      }
    `,
  ];

  /** What the script declares - `null` until a run has said, which is not the same thing as
   * a script that declares nothing. */
  @property({ attribute: false }) params: readonly ParamView[] | null = null;

  /** The values a person has set, by name. */
  @property({ attribute: false }) overrides: Overrides = {};

  override render() {
    if (this.params === null) return nothing;
    if (this.params.length === 0) {
      return html`<p class="empty">This script declares no parameters.</p>`;
    }
    return repeat(
      this.params,
      identity,
      (param) => html`
        <bench-param-field
          name=${param.name}
          label=${param.label}
          kind=${param.kind}
          .min=${param.min}
          .max=${param.max}
          .step=${param.step}
          .choices=${param.choices ?? []}
          .value=${this.overrides[param.name] ?? param.default}
          ?set=${Object.hasOwn(this.overrides, param.name)}
        ></bench-param-field>
      `,
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-params": BenchParams;
  }
}
