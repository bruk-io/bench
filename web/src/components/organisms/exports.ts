/** The files a run made, to take away: the whole project's, or one part's.
 *
 * decision-12 gives outputs one home, beside their subject: the project's inspector lists every
 * file and *Download all*, a part's lists only its own - the sheets it is cut from, its body for
 * the printer, its own drawing. This was the bottom panel's Files tab and the rail's Sheets
 * container, which said the same thing twice; a sheet's row here does both jobs, taking the
 * sheet away as SVG or DXF, and opening it beside the script on a click on its picture.
 *
 * Everything comes down as properties, and a click goes back up: `file-save`, `files-save-all`,
 * `sheet-open` and `slicer-open`. The grouping itself is `exports.ts`'s, which is pure.
 *
 * *Open in slicer* (task-86) sits on every row a printer reads - the run's 3MF and each part's
 * STL - when a host is serving the project (`slicer`), since it is the host that writes the
 * file into the project's `prints/` and opens it. How each one went comes back down as
 * `opening`, and is said under its row, where the click was.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";

import { type Download, type Row, layout, partLayout } from "../../exports";
import type { SheetView } from "../../scene";
import "../molecules/file-row";
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

/** A file a person asked to open in the host's slicer: its name and what is in it (base64). */
export interface SlicerOpenDetail {
  readonly name: string;
  readonly data: string;
}

/** How opening one file in the slicer is going: on its way, opened - and in which slicer, as
 * the host said it - or refused, with the host's reason in its own words. */
export type Opening =
  | { readonly state: "opening" }
  | { readonly state: "opened"; readonly message: string }
  | { readonly state: "failed"; readonly message: string };

/** Which sheet a person asked to look at. */
export interface SheetOpenDetail {
  readonly name: string;
}

@customElement("bench-exports")
export class BenchExports extends LitElement {
  static override styles = [
    base,
    buttons,
    css`
      /* One column the width of the inspector, never wider: a row's name is what gives way,
         so every row's buttons stay in reach. */
      :host {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 2px;
      }

      #outputs {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
      }

      .quiet {
        margin: 0;
        font-size: 12px;
        color: var(--fg-dim);
      }

      .group {
        margin: 6px 0 2px;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--fg-faint);
      }

      /* The sheet's picture is the way to open it: big enough to read, beside the script. */
      .sheet {
        flex: none;
        width: 48px;
        height: 32px;
        padding: 0;
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 4px;
        box-shadow: none;
        overflow: hidden;
      }

      .sheet img {
        width: 100%;
        height: 100%;
        object-fit: contain;
      }

      bench-file-row button:not(.sheet) {
        height: 22px;
        min-width: 38px;
        padding: 0 6px;
        font-size: 10.5px;
        font-weight: 600;
        box-shadow: none;
      }

      .all {
        justify-self: start;
        margin-top: 8px;
      }

      /* How opening a file in the slicer went, under the row it was asked from. */
      .opening {
        margin: 0 0 4px;
        font-size: 11px;
        line-height: 1.35;
        color: var(--fg-dim);
        overflow-wrap: anywhere;
      }

      .opening.failed {
        color: var(--danger);
      }
    `,
  ];

  /** The sheets the parts were nested onto. */
  @property({ attribute: false }) sheets: readonly SheetView[] = [];

  /** Every file the run made, by name; STL and 3MF as base64. */
  @property({ attribute: false }) files: Readonly<Record<string, string>> = {};

  /** The part whose files these are - or `null` for the whole project's, with *Download all*. */
  @property({ attribute: false }) onlyPart: { readonly ref: string; readonly label: string } | null = null;

  /** Whether a host is serving the project, and so can open a file in its slicer. */
  @property({ type: Boolean }) slicer = false;

  /** How each file asked for in the slicer is going, by name. */
  @property({ attribute: false }) opening: Readonly<Record<string, Opening>> = {};

  override render() {
    const { sheets, printed, others } =
      this.onlyPart === null ? layout(this.sheets, this.files) : partLayout(this.onlyPart, this.sheets, this.files);
    if (sheets.length + printed.length + others.length === 0) {
      return html`<p class="quiet">
        ${this.onlyPart === null ? "This run made no file to take away." : "This part has no file of its own."}
      </p>`;
    }
    return html`
      <div id="outputs">
        ${sheets.length === 0 ? nothing : html`<p class="group">sheets (${sheets.length})</p>`}
        ${sheets.map((row) => this.row(row, true))}
        ${printed.length === 0
          ? nothing
          : html`<p class="group">for the printer (${printed.length})</p>
              ${printed.map((row) => this.row(row, false, this.slicer))}`}
        ${others.length === 0
          ? nothing
          : html`<p class="group">other files (${others.length})</p>
              ${others.map((row) => this.row(row, false))}`}
      </div>
      ${this.onlyPart === null
        ? html`<button id="zip" class="primary all" type="button" @click=${this.saveAll}>Download all</button>`
        : nothing}
    `;
  }

  private row(row: Row, sheet: boolean, slicer = false) {
    const opening = slicer ? this.opening[row.name] : undefined;
    return html`
      <bench-file-row name=${row.name} meta=${row.meta}>
        ${sheet && row.preview !== undefined
          ? html`<button
              slot="preview"
              class="sheet"
              type="button"
              title="Open ${row.name} beside the script"
              @click=${() => {
                this.open(row.name);
              }}
            >
              <img alt="" src=${row.preview} />
            </button>`
          : nothing}
        ${row.downloads.map(
          (download) => html`
            <button
              type="button"
              @click=${() => {
                this.save(download);
              }}
            >
              ${download.label}
            </button>
          `,
        )}
        ${slicer
          ? html`<button
              class="slicer"
              type="button"
              title="Write ${row.name} into the project's prints folder and open it in the slicer"
              ?disabled=${opening?.state === "opening"}
              @click=${() => {
                this.openInSlicer(row);
              }}
            >
              Open in slicer
            </button>`
          : nothing}
      </bench-file-row>
      ${opening === undefined
        ? nothing
        : html`<p class="opening ${opening.state}" role="status" data-file=${row.name}>
            ${opening.state === "opening" ? `Opening ${row.name} in the slicer…` : opening.message}
          </p>`}
    `;
  }

  private openInSlicer(row: Row): void {
    const [download] = row.downloads;
    if (download === undefined) return;
    this.dispatchEvent(
      new CustomEvent<SlicerOpenDetail>("slicer-open", {
        bubbles: true,
        composed: true,
        detail: { name: download.name, data: download.data },
      }),
    );
  }

  private open(name: string): void {
    this.dispatchEvent(
      new CustomEvent<SheetOpenDetail>("sheet-open", { bubbles: true, composed: true, detail: { name } }),
    );
  }

  private save({ name, data }: Download): void {
    this.dispatchEvent(
      new CustomEvent<FileSaveDetail>("file-save", { bubbles: true, composed: true, detail: { name, data } }),
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
    "bench-exports": BenchExports;
  }

  interface HTMLElementEventMap {
    "file-save": CustomEvent<FileSaveDetail>;
    "files-save-all": CustomEvent<FilesSaveAllDetail>;
    "sheet-open": CustomEvent<SheetOpenDetail>;
    "slicer-open": CustomEvent<SlicerOpenDetail>;
  }

  /** The two saves bubble out of every shadow root and are listened for on the document,
   * which has an event map of its own. */
  interface DocumentEventMap {
    "file-save": CustomEvent<FileSaveDetail>;
    "files-save-all": CustomEvent<FilesSaveAllDetail>;
    "slicer-open": CustomEvent<SlicerOpenDetail>;
  }
}
