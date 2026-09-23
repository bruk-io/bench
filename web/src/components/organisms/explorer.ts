/** The sidebar's Files container: a switcher naming the open project, and the open project's
 * own files under it (decision-9, task-48).
 *
 * VS Code's split, which the container used to have the wrong way round: which folder is open
 * is a different control from what is in it, and used a hundred times less often. So the rare
 * act - another project, a new one, one from disk, a download - is one line at the top, a menu
 * behind the open project's name; the rest of the container is the project itself:
 * `bench.toml`, its scripts, and the meshes dropped into it, each a row that opens in the editor
 * group on a click. The actions that were a toolbar acting on "the current file" belong to the
 * row they act on now, behind its own `⋯` - a button rather than a hover, because a tablet has
 * no hover - since there is a row under the pointer that says which file is meant.
 *
 * Everything a person asks for goes up as an event, and changing the workspace, the host or the
 * file system is the page's to do: `project-open`, `project-new`, `project-import`,
 * `project-download`, `project-rename`, `project-delete` and `project-duplicate` from the
 * switcher; `file-open`, `file-rename`, `file-delete` and `file-duplicate` from the tree. A name
 * is checked here before it is sent, with the same functions the page applies, so the reason
 * one will not do is said beside the box it was typed in.
 *
 * **A delete says where the files go, before and after.** Nothing is unlinked: a project's
 * directory, or one of its files, moves into `.trash/` under the host's projects root
 * (`server/projects.ts`), and the question names that directory before it is answered; the
 * page says where it went once it has.
 *
 * **Read-only is a real mode** (task-47): a project somebody else is writing lists its files
 * and opens them, and offers no action on a row that would write. Duplicating it is still on
 * offer - that makes a project of one's own.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property, query, state } from "lit/decorators.js";

import { nameProblem, normalized, scriptName, scriptNameProblem } from "../../files";
import { DismissController } from "../controllers/dismiss";
import { base, buttons, disclosure } from "../styles";

/** A project, or a file in the open one, a person asked about by name. */
export interface NameDetail {
  readonly name: string;
}

/** A project or a file and the name it is to have, already read as one. */
export interface RenameDetail {
  readonly from: string;
  readonly to: string;
}

/** The files a person picked to open: scripts, and the values files beside them. */
export interface ImportDetail {
  readonly files: readonly File[];
}

/** What the open project holds, as the tree lists it. */
export interface ProjectFiles {
  /** Its scripts, in the order their tabs take: the entry first, the rest by name. */
  readonly scripts: readonly string[];
  /** The script a fresh open runs - `[project] entry`. */
  readonly entry: string;
  /** The meshes in its directory, by name. */
  readonly meshes: readonly string[];
}

/** The values document every project has one of. */
const DOCUMENT = "bench.toml";

/** Which row's actions are showing, if any: a project in the switcher or a file in the tree. */
type Target = { readonly kind: "project" | "file"; readonly name: string };

type Mode =
  | { readonly kind: "list" }
  | { readonly kind: "rename"; readonly target: Target }
  | { readonly kind: "delete"; readonly target: Target };

const LIST: Mode = { kind: "list" };

const same = (a: Target | null, b: Target): boolean => a !== null && a.kind === b.kind && a.name === b.name;

@customElement("bench-explorer")
export class BenchExplorer extends LitElement {
  static override styles = [
    base,
    buttons,
    disclosure,
    css`
      :host {
        position: relative;
        display: flex;
        flex-direction: column;
        min-height: 0;
        overflow: hidden;
      }

      .switcher {
        flex: none;
        padding: 4px 6px;
        border-bottom: 1px solid var(--line);
      }

      #project-switcher {
        width: 100%;
        justify-content: flex-start;
        gap: 6px;
        padding: 0 6px;
        font-family: var(--mono);
        font-weight: 600;
      }

      #project-switcher .name {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-align: left;
        text-overflow: ellipsis;
      }

      .menu {
        position: absolute;
        top: 36px;
        right: 6px;
        left: 6px;
        z-index: 20;
        display: flex;
        flex-direction: column;
        max-height: calc(100% - 44px);
        padding: 4px;
        background: var(--panel);
        border: 1px solid var(--line-strong);
        border-radius: 10px;
        box-shadow: var(--shadow-pop);
      }

      .menu[hidden] {
        display: none;
      }

      .list {
        flex: 1;
        min-height: 0;
        margin: 0;
        padding: 2px 0;
        overflow: auto;
        list-style: none;
      }

      .line {
        display: flex;
        align-items: center;
      }

      .row {
        flex: 1;
        min-width: 0;
        height: 24px;
        justify-content: flex-start;
        gap: 6px;
        padding: 0 8px;
        background: none;
        border: none;
        border-radius: 0;
        box-shadow: none;
        font-family: var(--mono);
        font-weight: 400;
      }

      .row:hover:not(:disabled) {
        background: var(--panel-2);
        border-color: transparent;
      }

      .row[aria-current="true"],
      .row[aria-current="true"]:hover {
        color: var(--accent);
        background: var(--accent-soft);
      }

      .row .name {
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .tag {
        color: var(--fg-faint);
        font-family: var(--sans, inherit);
        font-size: 10px;
      }

      .more {
        flex: none;
        width: 24px;
        height: 24px;
        padding: 0;
        color: var(--fg-dim);
        background: none;
        border: none;
        box-shadow: none;
      }

      .acts {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        padding: 2px 8px 6px 20px;
      }

      .group {
        margin: 8px 0 2px;
        padding: 0 8px;
        color: var(--fg-dim);
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }

      .foot {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        padding: 6px 4px 2px;
        border-top: 1px solid var(--line);
      }

      /* The picker is a button here; the input the browser needs is not on screen. */
      #project-pick {
        display: none;
      }

      .ask {
        display: grid;
        gap: 8px;
        padding: 8px;
      }

      .ask p,
      label,
      .said {
        margin: 0;
        font-size: 12px;
        overflow-wrap: anywhere;
      }

      .said {
        flex: none;
        padding: 6px 8px;
        color: var(--fg-dim);
        border-top: 1px solid var(--line);
      }

      .said[hidden] {
        display: none;
      }

      code {
        font-family: var(--mono);
        font-size: 11px;
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

  /** Every project under the root, in the order to list them. */
  @property({ attribute: false }) projects: readonly string[] = [];

  /** The project that is open. */
  @property({ attribute: false }) current = "";

  /** What the open project holds. */
  @property({ attribute: false }) files: ProjectFiles = { scripts: [], entry: "", meshes: [] };

  /** The file in front in the editor group - a script, or `bench.toml` - marked in the tree. */
  @property({ attribute: false }) front = "";

  /** Whether the open project is only being read here (task-47). */
  @property({ attribute: false }) readOnly = false;

  /** The host's projects root, which a delete names before it moves anything into its trash. */
  @property({ attribute: false }) root = "";

  /** A line the page has to say at the foot of the container - where a delete put what it
   * moved - or `null` for nothing. */
  @property({ attribute: false }) said: string | null = null;

  @state() private mode: Mode = LIST;

  /** Whether the switcher's menu is open. */
  @state() private switching = false;

  /** The row whose actions are showing. */
  @state() private acting: Target | null = null;

  /** The name being typed, while renaming. */
  @state() private draft = "";

  // No initializer: `@query` is a getter on the prototype, as in `param-field.ts`.
  @query("#file-name") private nameBox!: HTMLInputElement | null;

  @query("#project-pick") private picker!: HTMLInputElement | null;

  constructor() {
    super();
    new DismissController(this, () => {
      this.switching = false;
    });
  }

  override render() {
    switch (this.mode.kind) {
      case "rename":
        return this.renaming(this.mode.target);
      case "delete":
        return this.deleting(this.mode.target);
      case "list":
        return this.listing();
    }
  }

  // ---- the switcher -----------------------------------------------------------------

  private switcher() {
    return html`
      <div class="switcher">
        <button
          id="project-switcher"
          class="ghost disclosure"
          type="button"
          aria-haspopup="true"
          aria-expanded=${this.switching ? "true" : "false"}
          title="The open project - switch to another, or make one"
          @click=${this.toggle}
        >
          <span class="name">${this.current}</span>
        </button>
      </div>
      <div id="projects" class="menu" ?hidden=${!this.switching}>
        <ul class="list" aria-label="Your projects">
          ${this.projects.map((name) => this.projectRow(name))}
        </ul>
        <div class="foot">
          <button id="project-new" class="small ghost" type="button" @click=${this.create}>+ New</button>
          <button
            id="project-import"
            class="small ghost"
            type="button"
            title="Open a script from disk, with the .toml beside it if you pick that too"
            @click=${this.pick}
          >
            Open…
          </button>
          <button
            id="project-download"
            class="small ghost"
            type="button"
            title="Save the open project as its files - its scripts and its values"
            @click=${this.download}
          >
            Download
          </button>
          <input
            id="project-pick"
            type="file"
            accept=".py,.toml"
            multiple
            aria-label="Scripts and values files to open"
            @change=${this.picked}
          />
        </div>
      </div>
    `;
  }

  private projectRow(name: string) {
    const target: Target = { kind: "project", name };
    // Renaming or deleting the project somebody else is writing is theirs to do, not this
    // tab's; duplicating it makes one of this tab's own.
    const held = this.readOnly && name === this.current;
    return html`
      <li>
        <div class="line">
          <button
            class="row project"
            type="button"
            aria-current=${name === this.current ? "true" : "false"}
            @click=${() => this.choose(name)}
          >
            <span class="name">${name}</span>
          </button>
          ${this.more(target)}
        </div>
        ${same(this.acting, target)
          ? html`<div class="acts">
              ${held ? nothing : html`<button class="small ghost" type="button" @click=${() => this.startRename(target)}>Rename…</button>`}
              <button class="small ghost" type="button" @click=${() => this.duplicate(target)}>Duplicate</button>
              ${held ? nothing : html`<button class="small ghost danger" type="button" @click=${() => this.startDelete(target)}>Delete…</button>`}
            </div>`
          : nothing}
      </li>
    `;
  }

  // ---- the tree ---------------------------------------------------------------------

  private listing() {
    const { scripts, entry, meshes } = this.files;
    return html`
      ${this.switcher()}
      <ul class="list" aria-label=${`Files in ${this.current}`}>
        <li class="line">${this.fileRow(DOCUMENT, "the project's values, placement and entry")}</li>
        ${scripts.map(
          (name) => html`
            <li>
              <div class="line">
                ${this.fileRow(name, name === entry ? "the script a fresh open runs" : "", name === entry ? "entry" : "")}
                ${this.readOnly ? nothing : this.more({ kind: "file", name })}
              </div>
              ${this.scriptActions(name)}
            </li>
          `,
        )}
        ${meshes.length === 0
          ? nothing
          : html`
              <li class="group" id="meshes-head">References</li>
              ${meshes.map(
                (name) => html`
                  <li>
                    <div class="line">
                      ${this.fileRow(name, "a body dropped on the view")}
                      ${this.readOnly ? nothing : this.more({ kind: "file", name })}
                    </div>
                    ${same(this.acting, { kind: "file", name }) && !this.readOnly
                      ? html`<div class="acts">
                          <button class="small ghost danger" type="button" @click=${() => this.startDelete({ kind: "file", name })}>
                            Delete…
                          </button>
                        </div>`
                      : nothing}
                  </li>
                `,
              )}
            `}
      </ul>
      <p class="said" role="status" ?hidden=${this.said === null}>${this.said ?? nothing}</p>
    `;
  }

  private fileRow(name: string, title: string, tag = "") {
    return html`
      <button
        class="row file"
        type="button"
        title=${title}
        data-file=${name}
        aria-current=${name === this.front ? "true" : "false"}
        @click=${() => this.send<NameDetail>("file-open", { name })}
      >
        <span class="name">${name}</span>${tag === "" ? nothing : html`<span class="tag">${tag}</span>`}
      </button>
    `;
  }

  private scriptActions(name: string) {
    const target: Target = { kind: "file", name };
    if (this.readOnly || !same(this.acting, target)) return nothing;
    const last = this.files.scripts.length <= 1;
    return html`
      <div class="acts">
        <button class="small ghost" type="button" @click=${() => this.startRename(target)}>Rename…</button>
        <button class="small ghost" type="button" @click=${() => this.duplicate(target)}>Duplicate</button>
        <button
          class="small ghost danger"
          type="button"
          ?disabled=${last}
          title=${last ? "A project keeps at least one script - delete the project instead" : ""}
          @click=${() => this.startDelete(target)}
        >
          Delete…
        </button>
      </div>
    `;
  }

  /** The `⋯` that shows a row's actions, and hides them again. */
  private more(target: Target) {
    const open = same(this.acting, target);
    return html`
      <button
        class="more"
        type="button"
        aria-label=${`Actions for ${target.name}`}
        aria-expanded=${open ? "true" : "false"}
        @click=${() => (this.acting = same(this.acting, target) ? null : target)}
      >
        ⋯
      </button>
    `;
  }

  // ---- asking -----------------------------------------------------------------------

  private problem(target: Target): string | null {
    return target.kind === "project"
      ? nameProblem(this.projects, target.name, this.draft)
      : scriptNameProblem(this.files.scripts, target.name, this.draft);
  }

  private renaming(target: Target) {
    const problem = this.problem(target);
    return html`
      <form class="ask" @submit=${this.submitRename}>
        <label for="file-name">Rename ${target.name} to</label>
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
          <button id="file-rename-confirm" class="small primary" type="submit" ?disabled=${problem !== null}>
            Rename
          </button>
        </div>
      </form>
    `;
  }

  private deleting(target: Target) {
    const trash = this.root === "" ? html`<code>.trash/</code>` : html`<code>${this.root}/.trash/</code>`;
    const what =
      target.kind === "project"
        ? html`Delete <strong>${target.name}</strong>? Its directory moves on the host into ${trash}, with
            every file in it - its scripts, <code>bench.toml</code> and any meshes.`
        : html`Delete <strong>${target.name}</strong> from ${this.current}? It moves on the host into ${trash},
            in a folder named for the time and the project.`;
    return html`
      <div class="ask">
        <p id="file-delete-what">${what}</p>
        <p>Nothing is erased: move it back out of <code>.trash</code> to have it again.</p>
        <div class="footer">
          <button class="small ghost" type="button" @click=${this.back}>Cancel</button>
          <button id="file-delete-confirm" class="small danger" type="button" @click=${this.confirmDelete}>
            Move to trash
          </button>
        </div>
      </div>
    `;
  }

  private back(): void {
    this.mode = LIST;
  }

  private toggle(): void {
    this.switching = !this.switching;
    this.acting = null;
  }

  private startRename(target: Target): void {
    this.draft = target.name;
    this.acting = null;
    this.switching = false;
    this.mode = { kind: "rename", target };
    void this.updateComplete.then(() => {
      this.nameBox?.focus();
      this.nameBox?.select();
    });
  }

  private startDelete(target: Target): void {
    this.acting = null;
    this.switching = false;
    this.mode = { kind: "delete", target };
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
    if (this.mode.kind !== "rename") return;
    const { target } = this.mode;
    if (this.problem(target) !== null) return;
    const to = target.kind === "project" ? normalized(this.draft) : scriptName(this.draft);
    this.back();
    if (to !== target.name) this.send<RenameDetail>(`${target.kind}-rename`, { from: target.name, to });
  }

  private confirmDelete(): void {
    if (this.mode.kind !== "delete") return;
    const { target } = this.mode;
    this.back();
    this.send<NameDetail>(`${target.kind}-delete`, { name: target.name });
  }

  private duplicate(target: Target): void {
    this.acting = null;
    this.switching = false;
    this.send<NameDetail>(`${target.kind}-duplicate`, { name: target.name });
  }

  private create(): void {
    this.switching = false;
    this.send<null>("project-new", null);
  }

  private choose(name: string): void {
    this.switching = false;
    if (name !== this.current) this.send<NameDetail>("project-open", { name });
  }

  private download(): void {
    this.switching = false;
    this.send<NameDetail>("project-download", { name: this.current });
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
    this.switching = false;
    if (files.length > 0) this.send<ImportDetail>("project-import", { files });
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
    "project-open": CustomEvent<NameDetail>;
    "project-new": CustomEvent<null>;
    "project-import": CustomEvent<ImportDetail>;
    "project-download": CustomEvent<NameDetail>;
    "project-rename": CustomEvent<RenameDetail>;
    "project-delete": CustomEvent<NameDetail>;
    "project-duplicate": CustomEvent<NameDetail>;
    "file-open": CustomEvent<NameDetail>;
    "file-rename": CustomEvent<RenameDetail>;
    "file-delete": CustomEvent<NameDetail>;
    "file-duplicate": CustomEvent<NameDetail>;
  }
}
