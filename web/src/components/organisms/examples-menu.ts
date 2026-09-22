/** The Examples menu: the scripts that ship with the app, one click from the header.
 *
 * The names come down; a pick goes up as `example-pick`, and loading the script - replacing
 * the source, forgetting the overrides, running it - is the page's to do. The menu opens on
 * its button and shuts on a pick, a click outside it or Escape.
 */
import { LitElement, css, html } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { DismissController } from "../controllers/dismiss";
import { base, buttons, disclosure } from "../styles";

/** Which example a person picked, by its file name. */
export interface ExamplePickDetail {
  readonly name: string;
}

@customElement("bench-examples-menu")
export class BenchExamplesMenu extends LitElement {
  static override styles = [
    base,
    buttons,
    disclosure,
    css`
      :host {
        position: relative;
        display: inline-block;
      }

      .list {
        position: absolute;
        top: calc(100% + 6px);
        left: 0;
        z-index: 20;
        min-width: 220px;
        margin: 0;
        padding: 4px;
        list-style: none;
        background: var(--panel);
        border: 1px solid var(--line-strong);
        border-radius: 10px;
        box-shadow: var(--shadow-pop);
      }

      .list[hidden] {
        display: none;
      }

      .list button {
        width: 100%;
        justify-content: flex-start;
        font-family: var(--mono);
        font-weight: 400;
        background: none;
        border: none;
        border-radius: 6px;
        box-shadow: none;
      }

      .list button:hover:not(:disabled) {
        color: var(--accent);
        background: var(--accent-soft);
      }
    `,
  ];

  /** The example scripts, by file name, in the order to list them. */
  @property({ attribute: false }) names: readonly string[] = [];

  @state() private open = false;

  constructor() {
    super();
    new DismissController(this, () => {
      this.open = false;
    });
  }

  override render() {
    return html`
      <button
        id="examples-button"
        class="ghost disclosure"
        type="button"
        aria-haspopup="true"
        aria-expanded=${this.open ? "true" : "false"}
        @click=${this.toggle}
      >
        Examples
      </button>
      <ul id="examples" class="list" ?hidden=${!this.open}>
        ${this.names.map(
          (name) => html`
            <li><button type="button" @click=${() => this.pick(name)}>${name}</button></li>
          `,
        )}
      </ul>
    `;
  }

  private toggle(): void {
    this.open = !this.open;
  }

  private pick(name: string): void {
    this.open = false;
    this.dispatchEvent(
      new CustomEvent<ExamplePickDetail>("example-pick", {
        bubbles: true,
        composed: true,
        detail: { name },
      }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-examples-menu": BenchExamplesMenu;
  }

  interface HTMLElementEventMap {
    "example-pick": CustomEvent<ExamplePickDetail>;
  }
}
