/** What a run printed, across the bottom: its Output and its stderr, as two tabs, folded away
 * until somebody opens it.
 *
 * This panel used to hold everything a run said - what the checks found and the files it made
 * as well. decision-12 gives each of those one home beside its subject: a finding lives on the
 * part it is about and the files in the inspector's export, so what is left here is only what
 * the script itself said, which is about no part at all. It starts folded, because a clean run
 * that printed nothing has nothing to show here and the view is worth the room.
 *
 * The two streams stay two tabs rather than one box with both in it: a script's stderr is the
 * thing it did not expect to have to say, and running it together with what it meant to print
 * is how a warning goes unread.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { base, buttons } from "../styles";

/** Which tab of the panel is in front. */
export type PanelTab = "output" | "stderr";

const TABS: readonly PanelTab[] = ["output", "stderr"];

const LABEL: Readonly<Record<PanelTab, string>> = {
  output: "Output",
  stderr: "stderr",
};

@customElement("bench-panel")
export class BenchPanel extends LitElement {
  static override styles = [
    base,
    buttons,
    css`
      :host {
        display: flex;
        flex-direction: column;
        min-height: 0;
        background: var(--panel);
        border-top: 1px solid var(--line);
      }

      .tabs {
        flex: none;
        display: flex;
        align-items: stretch;
        height: 28px;
        padding: 0 6px 0 4px;
        border-bottom: 1px solid var(--line);
      }

      :host([collapsed]) .tabs {
        border-bottom: none;
      }

      .tab {
        height: auto;
        padding: 0 10px;
        gap: 5px;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        background: none;
        box-shadow: none;
        color: var(--fg-dim);
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }

      .tab:hover:not(:disabled) {
        background: none;
        border-color: transparent;
        color: var(--fg);
      }

      .tab[aria-selected="true"],
      .tab[aria-selected="true"]:hover {
        color: var(--fg);
        border-bottom-color: var(--fg);
      }

      .count {
        font: 500 10px/1 var(--mono);
        color: var(--fg-faint);
        letter-spacing: 0;
      }

      .count[data-bad="true"] {
        color: var(--warn);
      }

      .push {
        margin-left: auto;
      }

      .body {
        flex: 1;
        min-height: 0;
        overflow: auto;
        display: grid;
        align-content: start;
        gap: 8px;
        padding: 9px 12px 12px;
      }

      :host([collapsed]) .body {
        display: none;
      }

      pre.stream {
        margin: 0;
        font-family: var(--mono);
        font-size: 11px;
        white-space: pre-wrap;
        color: var(--fg);
      }

      .quiet {
        margin: 0;
        font-size: 12px;
        color: var(--fg-dim);
      }
    `,
  ];

  /** What the script printed. */
  @property() stdout = "";

  /** What the script wrote to stderr - `warnings.warn` included. */
  @property() stderr = "";

  /** Put away, so the drawing has the room - which is how it starts. Reflected, because the host
   * is sized by the page. */
  @property({ type: Boolean, reflect: true }) collapsed = true;

  @state() private tab: PanelTab = "output";

  /** Bring one tab to the front, and open the panel if it was put away. */
  show(tab: PanelTab): void {
    this.tab = tab;
    this.collapsed = false;
  }

  override render() {
    return html`
      <div class="tabs" role="tablist" aria-label="What the script printed">
        ${TABS.map((tab) => this.header(tab))}
        <button
          id="panel-toggle"
          class="tab push"
          type="button"
          title=${this.collapsed ? "Show the panel" : "Put the panel away"}
          aria-expanded=${this.collapsed ? "false" : "true"}
          @click=${this.toggle}
        >
          ${this.collapsed ? "▴" : "▾"}
        </button>
      </div>
      <div id="panel-body" class="body" role="tabpanel">${this.body()}</div>
    `;
  }

  private header(tab: PanelTab) {
    const said = (tab === "output" ? this.stdout : this.stderr).trim() !== "";
    return html`
      <button
        id=${`panel-tab-${tab}`}
        class="tab"
        type="button"
        role="tab"
        aria-selected=${tab === this.tab && !this.collapsed ? "true" : "false"}
        @click=${() => {
          this.choose(tab);
        }}
      >
        ${LABEL[tab]}
        ${said ? html`<span class="count" data-bad=${String(tab === "stderr")}>•</span>` : nothing}
      </button>
    `;
  }

  private body() {
    return this.tab === "output"
      ? this.stream("stdout", this.stdout, "This run printed nothing.")
      : this.stream("stderr", this.stderr, "This run wrote nothing to stderr.");
  }

  private stream(id: string, said: string, empty: string) {
    if (said.trim() === "") return html`<p class="quiet">${empty}</p>`;
    return html`<pre id=${id} class="stream">${said}</pre>`;
  }

  /** A click on a tab that is already in front puts the panel away, which is how every editor
   * with a panel behaves and saves a trip to the chevron. */
  private choose(tab: PanelTab): void {
    if (tab === this.tab && !this.collapsed) {
      this.collapsed = true;
      return;
    }
    this.show(tab);
  }

  private toggle(): void {
    this.collapsed = !this.collapsed;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-panel": BenchPanel;
  }
}
