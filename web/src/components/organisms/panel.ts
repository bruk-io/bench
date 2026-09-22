/** Everything a run said, across the bottom, as tabs.
 *
 * What the checks found, what the script printed on each of its two streams, and the files the
 * run made. These used to be a card floating over the drawing and a popover on the viewer bar,
 * both of them there because there was nowhere else to put them; with a panel there is
 * somewhere, and the rules get simpler - each tab says how much it holds, and a person opens
 * the one they want.
 *
 * The two streams stay two tabs rather than one box with both in it: a script's stderr is the
 * thing it did not expect to have to say, and running it together with what it meant to print
 * is how a warning goes unread.
 *
 * Everything it shows comes down as properties, and a click goes back up: `file-save`,
 * `files-save-all` and - from a finding that knows the line that asked for it - `goto-line`.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { type Download, layout } from "../../exports";
import type { SheetView, ViolationView } from "../../scene";
import "../atoms/callout";
import "../molecules/file-row";
import "../molecules/violation-list";
import { base, buttons } from "../styles";

/** One file to save: what the file is called and what is in it, as the scene carries it. */
export interface FileSaveDetail {
  readonly name: string;
  readonly data: string;
}

/** Every file the run made, to go together. */
export interface FilesSaveAllDetail {
  readonly files: Readonly<Record<string, string>>;
}

/** Which tab of the panel is in front. */
export type PanelTab = "problems" | "output" | "stderr" | "files";

const TABS: readonly PanelTab[] = ["problems", "output", "stderr", "files"];

const LABEL: Readonly<Record<PanelTab, string>> = {
  problems: "Problems",
  output: "Output",
  stderr: "stderr",
  files: "Files",
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
        height: 30px;
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
        color: var(--danger);
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

      .error {
        margin: 0;
        font-family: var(--mono);
        font-size: 11px;
        white-space: pre-wrap;
      }

      pre.stream {
        margin: 0;
        font-family: var(--mono);
        font-size: 11px;
        white-space: pre-wrap;
        color: var(--fg);
      }

      ul {
        margin: 0;
        padding: 0 0 0 16px;
        font-size: 11px;
      }

      .quiet {
        margin: 0;
        font-size: 12px;
        color: var(--fg-dim);
      }

      .group {
        margin: 6px 0 0;
        font-size: 10.5px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--fg-dim);
      }

      bench-file-row .preview {
        flex: none;
        width: 56px;
        height: 34px;
        object-fit: contain;
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 4px;
      }

      bench-file-row button {
        height: 22px;
        min-width: 40px;
        padding: 0 7px;
        font-size: 10.5px;
        font-weight: 600;
        box-shadow: none;
      }

      .all {
        justify-self: start;
        margin-top: 4px;
      }
    `,
  ];

  /** Why the run failed, traceback and all; empty when it did not. */
  @property() error = "";

  /** What the checks found. */
  @property({ attribute: false }) violations: readonly ViolationView[] = [];

  /** What the nest declined to do. */
  @property({ attribute: false }) warnings: readonly string[] = [];

  /** What the script printed. */
  @property() stdout = "";

  /** What the script wrote to stderr - `warnings.warn` included. */
  @property() stderr = "";

  /** The sheets the parts were nested onto. */
  @property({ attribute: false }) sheets: readonly SheetView[] = [];

  /** Every file the run made, by name; STL and 3MF as base64. */
  @property({ attribute: false }) files: Readonly<Record<string, string>> = {};

  /** Put away, so the drawing has the room. Reflected, because the host is sized by the page. */
  @property({ type: Boolean, reflect: true }) collapsed = false;

  @state() private tab: PanelTab = "problems";

  /** How much the Problems tab is holding - what the rail's badge counts too. */
  get problems(): number {
    return this.violations.length + this.warnings.length + (this.error === "" ? 0 : 1);
  }

  /** Bring one tab to the front, and open the panel if it was put away. Called by the page
   * when a run fails, and by the rail's Problems button. */
  show(tab: PanelTab): void {
    this.tab = tab;
    this.collapsed = false;
  }

  override render() {
    return html`
      <div class="tabs" role="tablist" aria-label="What the run said">
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
    const count = this.counted(tab);
    return html`
      <button
        id=${`panel-tab-${tab}`}
        class="tab"
        type="button"
        role="tab"
        aria-selected=${tab === this.tab && !this.collapsed ? "true" : "false"}
        @click=${() => this.choose(tab)}
      >
        ${LABEL[tab]}
        ${count === ""
          ? nothing
          : html`<span class="count" data-bad=${String(tab === "problems" && this.problems > 0)}>
              ${count}
            </span>`}
      </button>
    `;
  }

  /** What a tab says it is holding: a number where one is meaningful, a dot where the only
   * question is whether the stream said anything at all. */
  private counted(tab: PanelTab): string {
    switch (tab) {
      case "problems":
        return this.problems === 0 ? "" : String(this.problems);
      case "output":
        return this.stdout.trim() === "" ? "" : "•";
      case "stderr":
        return this.stderr.trim() === "" ? "" : "•";
      case "files":
        return Object.keys(this.files).length === 0 ? "" : String(Object.keys(this.files).length);
    }
  }

  private body() {
    switch (this.tab) {
      case "problems":
        return this.problemsTab();
      case "output":
        return this.stream("stdout", this.stdout, "This run printed nothing.");
      case "stderr":
        return this.stream("stderr", this.stderr, "This run wrote nothing to stderr.");
      case "files":
        return this.filesTab();
    }
  }

  private problemsTab() {
    if (this.problems === 0) {
      return html`<p id="no-problems" class="quiet">Nothing was reported: the run is clean.</p>`;
    }
    return html`
      ${this.error === ""
        ? nothing
        : html`<bench-callout tone="danger"
            ><pre id="error" class="error">${this.error}</pre></bench-callout
          >`}
      ${this.violations.length === 0
        ? nothing
        : html`<bench-violation-list
            id="violations"
            .violations=${this.violations}
          ></bench-violation-list>`}
      ${this.warnings.length === 0
        ? nothing
        : html`
            <bench-callout id="warnings" tone="warn">
              <ul>
                ${this.warnings.map((warning) => html`<li>${warning}</li>`)}
              </ul>
            </bench-callout>
          `}
    `;
  }

  private stream(id: string, said: string, empty: string) {
    if (said.trim() === "") return html`<p class="quiet">${empty}</p>`;
    return html`<pre id=${id} class="stream">${said}</pre>`;
  }

  private filesTab() {
    const count = Object.keys(this.files).length;
    if (count === 0) {
      return html`<p class="quiet">This run made no file to take away.</p>`;
    }
    const { sheets, printed, others } = layout(this.sheets, this.files);
    return html`
      <div id="outputs">
        ${sheets.map((row) => this.row(row))}
        ${printed.length === 0
          ? nothing
          : html`<p class="group">for the printer (${printed.length})</p>
              ${printed.map((row) => this.row(row))}`}
        ${others.length === 0
          ? nothing
          : html`<p class="group">other files (${others.length})</p>
              ${others.map((row) => this.row(row))}`}
      </div>
      <button id="zip" class="primary all" type="button" @click=${this.saveAll}>
        Download all
      </button>
    `;
  }

  private row(row: { name: string; meta: string; downloads: readonly Download[]; preview?: string }) {
    return html`
      <bench-file-row name=${row.name} meta=${row.meta}>
        ${row.preview === undefined
          ? nothing
          : html`<img slot="preview" class="preview" alt="" src=${row.preview} />`}
        ${row.downloads.map(
          (download) => html`
            <button type="button" @click=${() => this.save(download)}>${download.label}</button>
          `,
        )}
      </bench-file-row>
    `;
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

  private save({ name, data }: Download): void {
    this.dispatchEvent(
      new CustomEvent<FileSaveDetail>("file-save", {
        bubbles: true,
        composed: true,
        detail: { name, data },
      }),
    );
  }

  private saveAll(): void {
    this.dispatchEvent(
      new CustomEvent<FilesSaveAllDetail>("files-save-all", {
        bubbles: true,
        composed: true,
        detail: { files: this.files },
      }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-panel": BenchPanel;
  }

  interface HTMLElementEventMap {
    "file-save": CustomEvent<FileSaveDetail>;
    "files-save-all": CustomEvent<FilesSaveAllDetail>;
  }

  /** Both bubble out of the panel's shadow root and are listened for on the document, which
   * has an event map of its own. */
  interface DocumentEventMap {
    "file-save": CustomEvent<FileSaveDetail>;
    "files-save-all": CustomEvent<FilesSaveAllDetail>;
  }
}
