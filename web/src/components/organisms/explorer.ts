/** The projects kept in this browser, as the sidebar's own container.
 *
 * What was a menu behind a button is a list that is simply there, which is what the rail buys:
 * the container is only on screen when a person asked for it, so it does not have to fold
 * itself away. The names come down with the one that is open; everything a person asks for
 * goes up as an event - `file-new`, `file-open`, `file-rename`, `file-delete`,
 * `file-duplicate`, `file-download`, `file-import` - and changing the workspace, or touching
 * the file system, is the page's to do. `file-import` carries the files a person picked and
 * nothing read out of them: reading is I/O, and this only asks.
 *
 * A new name is checked here before it is sent, with the same `nameProblem` the page applies,
 * so the reason a name will not do is said beside the box it was typed in. Delete asks once,
 * in place: a project lives nowhere else, so nothing brings a deleted one back - which is what
 * Download is for.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property, query, state } from "lit/decorators.js";

import { nameProblem, normalized } from "../../files";
import { base, buttons } from "../styles";

/** The file a person asked to open, or to delete. */
export interface FileNameDetail {
  readonly name: string;
}

/** A file and the name it is to have, already read as a file name. */
export interface FileRenameDetail {
  readonly from: string;
  readonly to: string;
}

/** The files a person picked to open: scripts, and the values files beside them. */
export interface FileImportDetail {
  readonly files: readonly File[];
}

type Mode = "list" | "rename" | "delete";

@customElement("bench-explorer")
export class BenchExplorer extends LitElement {
  static override styles = [
    base,
    buttons,
    css`
      :host {
        display: flex;
        flex-direction: column;
        min-height: 0;
        overflow: hidden;
      }

      .list {
        flex: 1;
        min-height: 0;
        margin: 0;
        padding: 2px 0;
        overflow: auto;
        list-style: none;
      }

      .row {
        width: 100%;
        height: 24px;
        justify-content: flex-start;
        padding: 0 8px;
        background: none;
        border: none;
        border-radius: 0;
        box-shadow: none;
      }

      .row:hover:not(:disabled) {
        background: var(--panel-2);
        border-color: transparent;
      }

      .file {
        overflow: hidden;
        font-family: var(--mono);
        font-weight: 400;
        text-overflow: ellipsis;
      }

      .file[aria-current="true"],
      .file[aria-current="true"]:hover {
        color: var(--accent);
        background: var(--accent-soft);
      }

      .actions {
        flex: none;
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        padding: 6px 8px;
        border-top: 1px solid var(--line);
      }

      /* The picker is a button here; the input the browser needs is not on screen. */
      #file-pick {
        display: none;
      }

      .ask {
        display: grid;
        gap: 8px;
        padding: 8px;
      }

      .ask p,
      label {
        margin: 0;
        font-size: 12px;
        overflow-wrap: anywhere;
      }

      input {
        height: 26px;
        padding: 0 8px;
        font: inherit;
        font-family: var(--mono);
        font-size: 12px;
        color: var(--fg);
        background: var(--bg);
        border: 1px solid var(--line-strong);
        border-radius: var(--radius);
      }

      input[aria-invalid="true"] {
        border-color: var(--danger);
      }

      .problem {
        font-size: 11px;
        color: var(--danger);
      }

      .problem[hidden] {
        display: none;
      }

      .footer {
        display: flex;
        justify-content: flex-end;
        gap: 6px;
      }

      button.danger {
        color: var(--danger);
      }
    `,
  ];

  /** Every file kept, in the order to list them. */
  @property({ attribute: false }) names: readonly string[] = [];

  /** The file that is open. */
  @property({ attribute: false }) current = "";

  @state() private mode: Mode = "list";

  /** The name being typed, while renaming. */
  @state() private draft = "";

  // No initializer: `@query` is a getter on the prototype, as in `param-field.ts`.
  @query("#file-name") private nameBox!: HTMLInputElement | null;

  @query("#file-pick") private picker!: HTMLInputElement | null;

  override render() {
    switch (this.mode) {
      case "rename":
        return this.renaming();
      case "delete":
        return this.deleting();
      case "list":
        return this.listing();
    }
  }

  private listing() {
    return html`
      <ul class="list" aria-label="Your scripts">
        ${this.names.map(
          (name) => html`
            <li>
              <button
                class="row file"
                type="button"
                aria-current=${name === this.current ? "true" : "false"}
                @click=${() => this.choose(name)}
              >
                ${name}
              </button>
            </li>
          `,
        )}
      </ul>
      <div class="actions">
        <button id="file-new" class="small ghost" type="button" @click=${this.create}>
          + New
        </button>
        <button id="file-rename" class="small ghost" type="button" @click=${this.startRename}>
          Rename…
        </button>
        <button id="file-delete" class="small ghost danger" type="button" @click=${this.startDelete}>
          Delete
        </button>
        <button
          id="file-duplicate"
          class="small ghost"
          type="button"
          title="A copy of this project, script and values both"
          @click=${this.duplicate}
        >
          Duplicate
        </button>
        <button
          id="file-download"
          class="small ghost"
          type="button"
          title="Save this project as its two files - the script and its values"
          @click=${this.download}
        >
          Download
        </button>
        <button
          id="file-open"
          class="small ghost"
          type="button"
          title="Open a script from disk, with the .toml beside it if you pick that too"
          @click=${this.pick}
        >
          Open…
        </button>
        <input
          id="file-pick"
          type="file"
          accept=".py,.toml"
          multiple
          aria-label="Scripts and values files to open"
          @change=${this.picked}
        />
      </div>
    `;
  }

  private renaming() {
    const problem = nameProblem(this.names, this.current, this.draft);
    return html`
      <form class="ask" @submit=${this.submitRename}>
        <label for="file-name">Rename ${this.current} to</label>
        <input
          id="file-name"
          type="text"
          spellcheck="false"
          autocomplete="off"
          aria-invalid=${problem === null ? "false" : "true"}
          aria-describedby="file-problem"
          .value=${this.draft}
          @input=${this.typed}
          @keydown=${this.keyed}
        />
        <p id="file-problem" class="problem" ?hidden=${problem === null}>${problem ?? nothing}</p>
        <div class="footer">
          <button class="small ghost" type="button" @click=${this.back}>Cancel</button>
          <button
            id="file-rename-confirm"
            class="small primary"
            type="submit"
            ?disabled=${problem !== null}
          >
            Rename
          </button>
        </div>
      </form>
    `;
  }

  private deleting() {
    return html`
      <div class="ask">
        <p>
          Delete <strong>${this.current}</strong>? It is not kept anywhere else, so it cannot be
          brought back.
        </p>
        <div class="footer">
          <button class="small ghost" type="button" @click=${this.back}>Cancel</button>
          <button id="file-delete-confirm" class="small danger" type="button" @click=${this.confirmDelete}>
            Delete
          </button>
        </div>
      </div>
    `;
  }

  private back(): void {
    this.mode = "list";
  }

  private startRename(): void {
    this.draft = this.current;
    this.mode = "rename";
    void this.updateComplete.then(() => {
      this.nameBox?.focus();
      this.nameBox?.select();
    });
  }

  private startDelete(): void {
    this.mode = "delete";
  }

  private typed(event: Event): void {
    this.draft = (event.target as HTMLInputElement).value;
  }

  /** Escape in the box goes back to the list rather than leaving the container. */
  private keyed(event: KeyboardEvent): void {
    if (event.key !== "Escape") return;
    event.preventDefault();
    this.back();
  }

  private submitRename(event: SubmitEvent): void {
    event.preventDefault();
    if (nameProblem(this.names, this.current, this.draft) !== null) return;
    const to = normalized(this.draft);
    const from = this.current;
    this.back();
    if (to !== from) this.send<FileRenameDetail>("file-rename", { from, to });
  }

  private create(): void {
    this.send<null>("file-new", null);
  }

  private choose(name: string): void {
    if (name !== this.current) this.send<FileNameDetail>("file-open", { name });
  }

  private confirmDelete(): void {
    const name = this.current;
    this.back();
    this.send<FileNameDetail>("file-delete", { name });
  }

  private duplicate(): void {
    this.send<FileNameDetail>("file-duplicate", { name: this.current });
  }

  private download(): void {
    this.send<FileNameDetail>("file-download", { name: this.current });
  }

  private pick(): void {
    this.picker?.click();
  }

  /** What was picked goes up as it is; the same files picked again are still an opening. */
  private picked(event: Event): void {
    const input = event.target;
    if (!(input instanceof HTMLInputElement)) return;
    const files = Array.from(input.files ?? []);
    input.value = "";
    if (files.length > 0) this.send<FileImportDetail>("file-import", { files });
  }

  private send<T>(type: string, detail: T): void {
    this.dispatchEvent(new CustomEvent<T>(type, { bubbles: true, composed: true, detail }));
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-explorer": BenchExplorer;
  }

  interface HTMLElementEventMap {
    "file-new": CustomEvent<null>;
    "file-open": CustomEvent<FileNameDetail>;
    "file-rename": CustomEvent<FileRenameDetail>;
    "file-delete": CustomEvent<FileNameDetail>;
    "file-duplicate": CustomEvent<FileNameDetail>;
    "file-download": CustomEvent<FileNameDetail>;
    "file-import": CustomEvent<FileImportDetail>;
  }
}
