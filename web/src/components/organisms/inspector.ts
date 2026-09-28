/** The inspector: the right-hand column, whose content follows the selection (decision-12).
 *
 * decision-12's rule is that every thing has one home and an action lives next to its subject,
 * and the subject is whatever is selected:
 *
 * - **nothing - the project**: its knobs, its parts each with a badge saying how it stands, the
 *   findings that are about no one part, the reference meshes it holds, and Export all;
 * - **a part**: what the checks found on it as a list of places - each a click away from being
 *   lit in the view - how it is made and, for a printed part, how it prints (which way up, on
 *   which face, and whether it fits the printer's bed - all worked out in Python), its faces as
 *   a tree (what the refs container was), and its own files;
 * - **a face**: its ref and *Insert ref*, its area, its normal when it is a plane, the findings
 *   that name it, and the tree of its part with its row revealed;
 * - **a reference mesh**: survey, detect faces and the placement pick.
 *
 * A run that failed says so at the top, whatever the subject: that is about the run, not about
 * a part.
 *
 * Nothing here selects itself, and nothing here holds a copy of the run: the page hands down the
 * subject and the scene's own lists as properties, and every click goes back up as an event -
 * `subject-pick` from the breadcrumb, a part row or a face's part, `insert-ref`, `insert-fit`,
 * `params-reset` and `refs-show-all` from here, and whatever the organisms inside it say
 * (`param-change`, `place-pick`, `ref-pick`, `ref-visibility`, `ref-isolate`, `reference-pick`,
 * `goto-line`, `file-save`, `files-save-all`, `sheet-open`, `slicer-open`, the reference tools'),
 * all composed, so the page listens on this one element.
 *
 * **The faces tree is one element across a part and its faces.** It is drawn by one template at
 * one place in the column for both subjects, so clicking a face in it - which makes the face the
 * subject - keeps the branches opened and the scroll, and a face clicked in the view reveals its
 * row in the tree the person was already reading.
 */
import { LitElement, css, html, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";

import type { Overrides } from "../../overrides";
import type { BedView, ParamView, PartView, SheetView, ViolationView } from "../../scene";
import { HOW_TO_SELECT, printerWords, upWords } from "../../status";
import {
  PROJECT,
  type Standing,
  type Subject,
  findingsNaming,
  findingsOn,
  findingsOnNoPart,
  partOf,
  partRefOf,
  standingOf,
  standingWords,
  within,
} from "../../subjects";
import "../atoms/callout";
import "../molecules/reference-list";
import "../molecules/violation-list";
import { base, buttons } from "../styles";
import "./exports";
import type { Opening } from "./exports";
import "./params";
import "./reference-tools";
import type { ReferenceToolsView } from "./reference-tools";
import "./refs-tree";

/** What a pair of picked faces would write, or why it cannot - `null` while there is no pair. */
export type FitState = { readonly text: string } | { readonly why: string } | null;

const plural = (count: number, one: string): string => (count === 1 ? one : `${one}s`);

/** The last step of a ref - what a face is called inside its part. */
const tail = (ref: string): string => ref.slice(ref.lastIndexOf("/") + 1);

@customElement("bench-inspector")
export class BenchInspector extends LitElement {
  static override styles = [
    base,
    buttons,
    css`
      :host {
        display: flex;
        flex-direction: column;
        min-width: 0;
        min-height: 0;
        background: var(--panel);
      }

      /* ---- the head: where the subject sits, and what is selected ---- */

      .head {
        flex: none;
        display: grid;
        gap: 5px;
        padding: 7px 10px 8px;
        border-bottom: 1px solid var(--line);
      }

      .crumbs {
        display: flex;
        align-items: baseline;
        gap: 4px;
        min-width: 0;
        font-size: 11px;
        color: var(--fg-faint);
        white-space: nowrap;
      }

      .crumb {
        min-width: 0;
        height: auto;
        padding: 0;
        border: none;
        background: none;
        box-shadow: none;
        color: var(--fg-dim);
        font-size: 11px;
        font-weight: 600;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .crumb:hover:not(:disabled) {
        background: none;
        color: var(--fg);
        text-decoration: underline;
      }

      .crumb[aria-current="page"] {
        color: var(--fg);
        cursor: default;
        text-decoration: none;
      }

      .crumb-tail {
        min-width: 0;
        color: var(--fg);
        font-weight: 600;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .picked {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        min-width: 0;
      }

      .selection {
        min-width: 0;
        max-width: 100%;
        font-size: 11.5px;
        color: var(--fg-faint);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .selection.is-set {
        font-family: var(--mono);
        font-size: 11px;
        color: var(--fg);
        background: color-mix(in srgb, var(--select) 14%, transparent);
        box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--select) 45%, transparent);
        border-radius: 5px;
        padding: 2px 7px;
      }

      /* Nothing to insert: say how to get something rather than show a dead button. */
      .picked button:disabled {
        display: none;
      }

      .fit-why {
        font-size: 11px;
        color: var(--fg-dim);
      }

      .fit-why:empty {
        display: none;
      }

      kbd {
        font: 10px var(--mono);
        opacity: 0.6;
      }

      .failed {
        flex: none;
        margin: 8px 10px 0;
      }

      .error {
        margin: 0;
        max-height: 30vh;
        overflow: auto;
        font-family: var(--mono);
        font-size: 11px;
        white-space: pre-wrap;
      }

      /* ---- the body: one section per thing about the subject ---- */

      .body {
        flex: 1;
        min-height: 0;
        overflow: auto;
        padding-bottom: 16px;
      }

      section {
        padding: 8px 10px 10px;
        border-bottom: 1px solid var(--line);
      }

      section:last-child {
        border-bottom: none;
      }

      .section-head {
        display: flex;
        align-items: center;
        gap: 6px;
        margin: 0 0 6px;
      }

      h2 {
        margin: 0;
        font-size: 10.5px;
        font-weight: 700;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: var(--fg-dim);
      }

      .count {
        font: 500 10px/1 var(--mono);
        color: var(--fg-faint);
      }

      .count:empty {
        display: none;
      }

      .push {
        margin-left: auto;
      }

      .quiet {
        margin: 0;
        font-size: 12px;
        color: var(--fg-dim);
      }

      .foot {
        margin: 6px 0 0;
        font-size: 11px;
        color: var(--fg-faint);
      }

      .title {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 0 6px;
        font-size: 13px;
        font-weight: 600;
        overflow-wrap: anywhere;
      }

      /* ---- a part, as a row of the project's list ---- */

      .parts {
        display: grid;
        gap: 1px;
        margin: 0 -4px;
      }

      .part {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        height: auto;
        min-height: 28px;
        padding: 3px 6px;
        border: none;
        border-radius: 5px;
        background: none;
        box-shadow: none;
        text-align: left;
      }

      .part:hover:not(:disabled) {
        background: var(--panel-2);
        border-color: transparent;
      }

      .part-name {
        flex: 1;
        min-width: 0;
        display: grid;
        font-family: var(--mono);
        font-size: 11.5px;
        font-weight: 500;
        overflow: hidden;
      }

      .part-name > span {
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .part-meta {
        font-family: var(--sans);
        font-size: 10.5px;
        font-weight: 400;
        color: var(--fg-faint);
      }

      .part[data-hidden="true"] .part-name {
        color: var(--fg-faint);
        font-style: italic;
      }

      /* How a part stands, in the words the status bar would use. Quiet for ok; the tone of
         the worst finding otherwise; dashed for what nothing measured, which is not a pass. */
      .badge {
        flex: none;
        padding: 1px 7px;
        border-radius: 999px;
        border: 1px solid var(--line);
        font-size: 10px;
        font-weight: 600;
        white-space: nowrap;
        color: var(--fg-faint);
      }

      .badge[data-standing="ok"] {
        color: var(--ok);
        background: var(--ok-soft);
        border-color: transparent;
      }

      .badge[data-standing="warning"] {
        color: var(--warn);
        background: var(--warn-soft);
        border-color: transparent;
      }

      .badge[data-standing="error"] {
        color: var(--danger);
        background: var(--danger-soft);
        border-color: transparent;
      }

      .badge[data-standing="unchecked"] {
        border-style: dashed;
      }

      /* ---- how a part prints, and what a face is ---- */

      dl {
        display: grid;
        grid-template-columns: max-content minmax(0, 1fr);
        gap: 3px 10px;
        margin: 0;
        font-size: 12px;
      }

      dt {
        color: var(--fg-faint);
      }

      dd {
        margin: 0;
        overflow-wrap: anywhere;
      }

      dd.mono {
        font-family: var(--mono);
        font-size: 11px;
      }

      dd[data-fits="false"] {
        color: var(--danger);
      }

      .over {
        display: block;
        margin-top: 2px;
        font-size: 11px;
        color: var(--fg-dim);
      }

      bench-refs-tree {
        margin: 0 -10px;
        max-height: 50vh;
      }
    `,
  ];

  /** What the inspector is about. */
  @property({ attribute: false }) subject: Subject = PROJECT;

  /** The open project's name - the breadcrumb's first step. */
  @property() project = "";

  /** The newest run's parts, refs, findings, the nest's warnings and its sheets and files. */
  @property({ attribute: false }) parts: readonly PartView[] = [];
  @property({ attribute: false }) refs: readonly string[] = [];
  @property({ attribute: false }) violations: readonly ViolationView[] = [];
  @property({ attribute: false }) warnings: readonly string[] = [];
  @property({ attribute: false }) sheets: readonly SheetView[] = [];
  @property({ attribute: false }) files: Readonly<Record<string, string>> = {};

  /** Whether a host is serving the project, so *Open in slicer* can be offered, and how each
   * file asked for in the slicer is going (task-86). */
  @property({ type: Boolean }) slicer = false;
  @property({ attribute: false }) opening: Readonly<Record<string, Opening>> = {};

  /** The printer's bed the printed parts are laid on, or `null` when nothing named one. */
  @property({ attribute: false }) bed: BedView | null = null;

  /** Why the newest run failed, traceback and all - or why nothing could run; empty when it
   * did not fail. */
  @property() error = "";

  /** What the script declares - `null` until a run has said - and the values a person set. */
  @property({ attribute: false }) params: readonly ParamView[] | null = null;
  @property({ attribute: false }) overrides: Overrides = {};

  /** Whether this tab is only reading the project, so a turned knob is not kept (task-47). */
  @property({ type: Boolean }) reading = false;

  /** The rows an eye has shut, by their own ref path - the page's set, drawn here. */
  @property({ attribute: false }) hiddenRefs: readonly string[] = [];

  /** The ref lit in the view: the selection, or a place of a finding picked from a list. */
  @property() lit: string | null = null;

  /** Whether *Insert ref* can write - something lit, and a project this tab may write. */
  @property({ type: Boolean }) insertable = false;

  /** task-61's second pick, and what it and the first would write. */
  @property() second: string | null = null;
  @property({ attribute: false }) fit: FitState = null;

  /** The meshes the project holds, the one on the view, and the tools for it. */
  @property({ attribute: false }) references: readonly string[] = [];
  @property({ attribute: false }) activeReference: string | null = null;
  @property({ attribute: false }) tools: ReferenceToolsView | null = null;

  override render() {
    return html`
      ${this.head()}
      ${this.error === ""
        ? nothing
        : html`<bench-callout class="failed" tone="danger"><pre id="error" class="error">${this.error}</pre></bench-callout>`}
      <div class="body">${this.lead()}${this.faces()}${this.exported()}</div>
    `;
  }

  // ---- the head --------------------------------------------------------------------

  private head() {
    const subject = this.subject;
    const part = this.subjectPart();
    const said =
      this.lit ?? (subject.kind === "reference" ? `reference: ${subject.file}` : HOW_TO_SELECT);
    const fit = this.fit;
    return html`
      <div class="head">
        <nav class="crumbs" aria-label="What the inspector is showing">
          <button
            id="crumb-project"
            class="crumb"
            type="button"
            aria-current=${subject.kind === "project" ? "page" : "false"}
            title="Show the project"
            @click=${() => {
              this.pickSubject(PROJECT);
            }}
          >
            ${this.project === "" ? "project" : this.project}
          </button>
          ${part === null
            ? nothing
            : html`<span aria-hidden="true">›</span>
                <button
                  id="crumb-part"
                  class="crumb"
                  type="button"
                  aria-current=${subject.kind === "part" ? "page" : "false"}
                  title="Show this part"
                  @click=${() => {
                    this.pickSubject({ kind: "part", ref: part.ref });
                  }}
                >
                  ${part.label}
                </button>`}
          ${subject.kind === "face"
            ? html`<span aria-hidden="true">›</span><span class="crumb-tail">${tail(subject.ref)}</span>`
            : subject.kind === "reference"
              ? html`<span aria-hidden="true">›</span><span class="crumb-tail">${subject.file}</span>`
              : nothing}
        </nav>
        <div class="picked">
          <span id="selection" class="selection ${this.lit === null && subject.kind !== "reference" ? "" : "is-set"}"
            >${said}</span
          >
          <button
            id="insert"
            type="button"
            class="small"
            title="Insert ref at the cursor (Ctrl/Cmd+I)"
            ?disabled=${!this.insertable}
            @click=${() => {
              this.plain("insert-ref");
            }}
          >
            Insert ref <kbd>⌘I</kbd>
          </button>
          <button
            id="insert-fit"
            type="button"
            class="small"
            title=${fit !== null && "text" in fit ? fit.text : fit?.why || "shift-click a face on another part"}
            ?disabled=${fit === null || !("text" in fit) || !this.insertable}
            @click=${() => {
              this.plain("insert-fit");
            }}
          >
            Insert fit
          </button>
          <span id="fit-why" class="fit-why">${fit !== null && "why" in fit ? fit.why : ""}</span>
        </div>
      </div>
    `;
  }

  // ---- what leads, by subject ------------------------------------------------------------

  private lead() {
    const subject = this.subject;
    switch (subject.kind) {
      case "project":
        return this.projectLead();
      case "part":
        return this.partLead(subject.ref);
      case "face":
        return this.faceLead(subject.ref);
      case "reference":
        return this.referenceLead(subject.file);
    }
  }

  private projectLead() {
    const count = this.params?.length ?? 0;
    const unplaced = findingsOnNoPart(this.violations, this.parts);
    return html`
      <section id="knobs" aria-labelledby="knobs-head">
        <div class="section-head">
          <h2 id="knobs-head">Knobs</h2>
          <span id="param-count" class="count">${count === 0 ? "" : String(count)}</span>
          <button
            id="reset"
            type="button"
            class="link push"
            ?disabled=${Object.keys(this.overrides).length === 0}
            @click=${() => {
              this.plain("params-reset");
            }}
          >
            reset
          </button>
        </div>
        <bench-params id="params" .params=${this.params} .overrides=${this.overrides}></bench-params>
        ${this.reading
          ? html`<p id="params-unkept" class="foot">
              Read-only here: these knobs turn and the model runs, but nothing turned is kept.
            </p>`
          : nothing}
      </section>
      <section id="parts" aria-labelledby="parts-head">
        <div class="section-head">
          <h2 id="parts-head">Parts</h2>
          <span class="count">${this.parts.length === 0 ? "" : String(this.parts.length)}</span>
          ${this.showAll()}
        </div>
        ${this.parts.length === 0
          ? html`<p class="quiet">Nothing has run yet.</p>`
          : html`<div class="parts">${this.parts.map((part) => this.partRow(part))}</div>`}
      </section>
      ${unplaced.length === 0 && this.warnings.length === 0
        ? nothing
        : html`<section id="project-findings" aria-labelledby="project-findings-head">
            <div class="section-head"><h2 id="project-findings-head">Findings on no one part</h2></div>
            ${unplaced.length === 0
              ? nothing
              : html`<bench-violation-list id="violations" .violations=${unplaced} .lit=${this.lit}></bench-violation-list>`}
            ${this.warnings.length === 0
              ? nothing
              : html`<bench-callout id="warnings" tone="warn">
                  <ul>
                    ${this.warnings.map((warning) => html`<li>${warning}</li>`)}
                  </ul>
                </bench-callout>`}
          </section>`}
      ${this.references.length === 0
        ? nothing
        : html`<section id="references" aria-labelledby="references-head">
            <div class="section-head"><h2 id="references-head">References</h2></div>
            <bench-reference-list
              .references=${this.references}
              .activeReference=${this.activeReference}
            ></bench-reference-list>
            <p class="foot">Choosing one puts it on the view: its survey, detect faces and placement are there.</p>
          </section>`}
    `;
  }

  private partRow(part: PartView) {
    const standing = standingOf(findingsOn(part.ref, this.violations));
    const hidden = this.hiddenRefs.some((one) => within(part.ref, one));
    return html`
      <button
        class="part"
        type="button"
        data-part=${part.ref}
        data-hidden=${String(hidden)}
        title="Show this part"
        @click=${() => {
          this.pickSubject({ kind: "part", ref: part.ref });
        }}
      >
        <span class="part-name">
          <span>${part.label}</span>
          <span class="part-meta">${this.madeOf(part)}${hidden ? " · hidden" : ""}</span>
        </span>
        ${this.badge(standing)}
      </button>
    `;
  }

  private badge(standing: Standing) {
    return html`<span class="badge" data-standing=${standing.kind}>${standingWords(standing)}</span>`;
  }

  /** What a part is made of and how, in a few words: "printed · PLA", "laser · 3 mm ply × 6". */
  private madeOf(part: PartView): string {
    const many = part.qty > 1 ? ` × ${String(part.qty)}` : "";
    if (part.process === "print") return `printed · ${part.stock.material}${many}`;
    return `${part.process} · ${String(part.stock.thickness)} mm ${part.stock.material}${many}`;
  }

  private partLead(ref: string) {
    const part = this.parts.find((one) => one.ref === ref);
    if (part === undefined) {
      return html`<section><p class="quiet">The newest run made no part called ${ref}.</p></section>`;
    }
    const found = findingsOn(part.ref, this.violations);
    return html`
      <section id="part-findings" aria-labelledby="part-findings-head">
        <div class="section-head">
          <h2 id="part-findings-head">Findings</h2>
          <span class="count">${found.length === 0 ? "" : String(found.length)}</span>
          <span class="push">${this.badge(standingOf(found))}</span>
        </div>
        ${found.length === 0
          ? html`<p id="no-problems" class="quiet">Nothing was reported about this part.</p>`
          : html`<bench-violation-list id="violations" .violations=${found} .lit=${this.lit}></bench-violation-list>`}
      </section>
      <section id="prints" aria-labelledby="prints-head">
        <div class="section-head"><h2 id="prints-head">How it is made</h2></div>
        <dl>
          <dt>process</dt>
          <dd>${part.process}</dd>
          <dt>stock</dt>
          <dd>
            ${part.stock.material}${part.process === "print" ? "" : `, ${String(part.stock.thickness)} mm`}
            ${part.stock.kerf > 0 ? `, kerf ${String(part.stock.kerf)} mm` : ""}
          </dd>
          <dt>quantity</dt>
          <dd>${part.qty}</dd>
          <dt>body</dt>
          <dd>${part.mesh === null ? "not built in this run" : "built"}</dd>
          ${this.printing(part)}
        </dl>
      </section>
    `;
  }

  /** How a printed part prints - which way up, on which face, and whether it fits the bed -
   * as Python worked it out; nothing for a part that is not printed. */
  private printing(part: PartView) {
    const printing = part.printing;
    if (printing === null) return nothing;
    const bed = this.bed;
    const face = printing.bed_face === null ? "" : `, on ${tail(printing.bed_face)}`;
    const chosen =
      bed === null
        ? ""
        : bed.said === "script"
          ? "the volume the script's check_fits asks about"
          : "the default printer - a script names another by asking check_fits about its volume";
    return html`
      <dt>prints</dt>
      <dd id="print-up">${upWords(printing.up)} up${face}</dd>
      <dt>bed</dt>
      <dd id="print-fits" data-fits=${printing.fits === null ? "" : String(printing.fits)} title=${chosen}>
        ${printing.fits === null || bed === null
          ? "no printer named to fit it on"
          : printing.fits
            ? `fits ${printerWords(bed)}`
            : html`does not fit ${printerWords(bed)}${printing.over === null ? nothing : html`<span class="over">${printing.over}</span>`}`}
      </dd>
    `;
  }

  private faceLead(ref: string) {
    const part = partOf(ref, this.parts);
    const frame = part?.frames[ref];
    const area = part?.areas[ref];
    const found = findingsNaming(ref, this.violations);
    return html`
      <section id="face" aria-labelledby="face-head">
        <div class="section-head"><h2 id="face-head">Face</h2></div>
        <dl>
          <dt>ref</dt>
          <dd class="mono">${ref}</dd>
          <dt>part</dt>
          <dd>
            ${part === null
              ? html`<span class="quiet">no part of this run</span>`
              : html`<button
                  class="crumb"
                  type="button"
                  @click=${() => {
                    this.pickSubject({ kind: "part", ref: part.ref });
                  }}
                >
                  ${part.label}
                </button>`}
          </dd>
          ${area === undefined
            ? nothing
            : html`<dt>area</dt>
                <dd id="face-area">${area.toFixed(1)} mm²</dd>`}
          ${frame === undefined
            ? nothing
            : html`<dt>normal</dt>
                <dd class="mono">${frame.normal.map((one) => one.toFixed(3)).join(", ")}</dd>`}
        </dl>
      </section>
      <section id="face-findings" aria-labelledby="face-findings-head">
        <div class="section-head">
          <h2 id="face-findings-head">Findings naming it</h2>
          <span class="count">${found.length === 0 ? "" : String(found.length)}</span>
        </div>
        ${found.length === 0
          ? html`<p class="quiet">No check named this face.</p>`
          : html`<bench-violation-list id="violations" .violations=${found} .lit=${this.lit}></bench-violation-list>`}
      </section>
    `;
  }

  private referenceLead(file: string) {
    const tools = file === this.activeReference ? this.tools : null;
    return html`
      <section id="reference-tools" aria-labelledby="reference-head">
        <div class="section-head"><h2 id="reference-head">Reference mesh</h2></div>
        ${tools === null
          ? html`<p class="quiet">${file} is not on the view.</p>`
          : html`<bench-reference-tools .view=${tools}></bench-reference-tools>`}
      </section>
    `;
  }

  // ---- the faces of a part, for the part and for each of its faces --------------------------

  private faces() {
    const part = this.subjectPart();
    if (part === null) return nothing;
    const refs = this.refs.filter((ref) => within(ref, part.ref));
    return html`
      <section id="faces" aria-labelledby="faces-head">
        <div class="section-head">
          <h2 id="faces-head">Faces</h2>
          <span id="refs-count" class="count">${refs.length === 0 ? "" : String(refs.length)}</span>
          ${this.showAll()}
        </div>
        <bench-refs-tree
          id="refs-tree"
          .refs=${refs}
          .selected=${this.lit}
          .flagged=${this.violations.flatMap((one) => [...one.refs])}
          .hiddenRefs=${this.hiddenRefs}
        ></bench-refs-tree>
      </section>
    `;
  }

  private showAll() {
    return html`<button
      id="refs-show-all"
      type="button"
      class="link push"
      title="Show every part and face again"
      ?disabled=${this.hiddenRefs.length === 0}
      @click=${() => {
        this.plain("refs-show-all");
      }}
    >
      show all
    </button>`;
  }

  // ---- what can be taken away ------------------------------------------------------------

  private exported() {
    const subject = this.subject;
    if (subject.kind === "face" || subject.kind === "reference") return nothing;
    const part = subject.kind === "part" ? (this.parts.find((one) => one.ref === subject.ref) ?? null) : null;
    if (subject.kind === "part" && part === null) return nothing;
    const count = Object.keys(this.files).length;
    return html`
      <section id="export" aria-labelledby="export-head">
        <div class="section-head">
          <h2 id="export-head">${part === null ? "Export" : "Export this part"}</h2>
          <span class="count">${part === null && count > 0 ? `${String(count)} ${plural(count, "file")}` : ""}</span>
        </div>
        <bench-exports
          .sheets=${this.sheets}
          .files=${this.files}
          .onlyPart=${part === null ? null : { ref: part.ref, label: part.label }}
          ?slicer=${this.slicer}
          .opening=${this.opening}
        ></bench-exports>
      </section>
    `;
  }

  // ---- helpers -----------------------------------------------------------------------------

  /** The part the subject is, or is on - `null` for the project and a reference. */
  private subjectPart(): PartView | null {
    const ref = partRefOf(this.subject, this.parts);
    return ref === null ? null : (this.parts.find((one) => one.ref === ref) ?? null);
  }

  private pickSubject(subject: Subject): void {
    this.dispatchEvent(new CustomEvent<Subject>("subject-pick", { bubbles: true, composed: true, detail: subject }));
  }

  private plain(type: "insert-ref" | "insert-fit" | "params-reset" | "refs-show-all"): void {
    this.dispatchEvent(new CustomEvent(type, { bubbles: true, composed: true }));
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-inspector": BenchInspector;
  }

  interface HTMLElementEventMap {
    "subject-pick": CustomEvent<Subject>;
    "insert-ref": CustomEvent<undefined>;
    "insert-fit": CustomEvent<undefined>;
    "params-reset": CustomEvent<undefined>;
    "refs-show-all": CustomEvent<undefined>;
  }
}
