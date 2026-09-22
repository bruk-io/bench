/** Everything the checks found, one row each, in the order the run reported them. */
import { LitElement, css, html } from "lit";
import { customElement, property } from "lit/decorators.js";

import type { ViolationView } from "../../scene";
import "./violation";
import { base } from "../styles";

@customElement("bench-violation-list")
export class BenchViolationList extends LitElement {
  static override styles = [
    base,
    css`
      :host {
        display: grid;
        gap: 6px;
      }
    `,
  ];

  @property({ attribute: false }) violations: readonly ViolationView[] = [];

  override render() {
    return this.violations.map(
      (found) => html`
        <bench-violation
          severity=${found.severity}
          check=${found.check}
          message=${found.message}
          .refs=${found.refs}
          .line=${found.line}
        ></bench-violation>
      `,
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-violation-list": BenchViolationList;
  }
}
