/** Every name a run made, as a tree - and the other half of bench's one round-trip.
 *
 * A run hands down its refs as paths: `drawer-front-1`, `drawer-front-1/pull`. Nested on the
 * separator they are a tree, and a tree is how a maker reads what a script named without
 * hunting for it on the drawing.
 *
 * Selection is one thing seen from two places. `selected` comes down from the page - set by a
 * click on a face as readily as by a click in here - and setting it opens whatever ancestors
 * were shut and scrolls the row into view. A click on a row goes up as `ref-pick` and nothing
 * more: this component never selects itself, so the two directions cannot fight or loop.
 *
 * Visibility is the same shape, one more time (task-67). `hidden` comes down from the page,
 * every row's own eye draws hidden or not by it, and a click on an eye goes up as
 * `ref-visibility` - the ref and the state it should now have - never a new `hidden` array:
 * this component does not know whether hiding one row should turn another back on, so it says
 * what changed and lets the page decide what the whole set becomes. `ref-isolate` off a
 * part's own "only" is the same shape at the scale of a whole assembly.
 */
import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { ifDefined } from "lit/directives/if-defined.js";

import { base } from "../styles";

/** Which ref a person picked off the tree. */
export interface RefPickDetail {
  readonly ref: string;
}

/** A row's eye was clicked: `ref` and the state it should now have. The page owns
 * `hidden` - this never guesses at what the new set should be, only what changed. */
export interface RefVisibilityDetail {
  readonly ref: string;
  readonly hidden: boolean;
}

/** A part row's "only" was clicked: show `ref` and hide every other part. */
export interface RefIsolateDetail {
  readonly ref: string;
}

/** Which dropped body a person picked off the References group. */
export interface ReferencePickDetail {
  readonly file: string;
}

/** One name in the tree: its whole path, the last step of it, and what hangs under it. */
interface Node {
  readonly path: string;
  readonly name: string;
  readonly children: Node[];
}

/** One row as it is drawn: the node, how deep it sits, and whether it is open. */
interface Row {
  readonly node: Node;
  readonly depth: number;
  readonly open: boolean;
}

/** The refs as a tree. A path whose parent nothing named still gets a node, so
 * `a/b` alone is `a` with `b` under it rather than one row called `a/b`. */
/** Names in the order a person counts them: `bottom-2` before `bottom-10`.
 *
 * A plain sort is lexicographic, and a part's faces are numbered - `bottom-1` to `bottom-19`
 * on one panel of the cabinet - so it files all the teens ahead of the twos. The scene
 * already hands its refs over in counting order; this is here so building the tree does not
 * scramble what arrived sorted. */
const counting = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });

export function treeOf(refs: readonly string[]): Node[] {
  const roots: Node[] = [];
  const byPath = new Map<string, Node>();
  for (const ref of [...refs].sort((a, b) => counting.compare(a, b))) {
    let path = "";
    let siblings = roots;
    for (const step of ref.split("/")) {
      path = path === "" ? step : `${path}/${step}`;
      let found = byPath.get(path);
      if (found === undefined) {
        found = { path, name: step, children: [] };
        byPath.set(path, found);
        siblings.push(found);
      }
      siblings = found.children;
    }
  }
  return roots;
}

/** Every path above `ref`, nearest last: `a/b/c` gives `a` and `a/b`. */
function ancestors(ref: string): string[] {
  const steps = ref.split("/");
  return steps.slice(0, -1).map((_, at) => steps.slice(0, at + 1).join("/"));
}

/** Whether `ref` is `flagged` or names something inside it - the same "inside" the viewer
 * paints by, so a shut parent still shows that something under it was reported. */
const within = (ref: string, flagged: string): boolean =>
  ref === flagged || flagged.startsWith(`${ref}/`);

/** Whether `path` is under `ancestor` - the other direction from `within`: is this row
 * inside a hidden one, rather than does a hidden ref sit inside this row. */
const under = (path: string, ancestor: string): boolean => path.startsWith(`${ancestor}/`);

@customElement("bench-refs-tree")
export class BenchRefsTree extends LitElement {
  static override styles = [
    base,
    css`
      :host {
        display: block;
        overflow: auto;
        padding: 4px 0 8px;
      }

      .row {
        display: flex;
        align-items: center;
        gap: 4px;
        width: 100%;
        padding: 2px 8px 2px 4px;
        border: none;
        border-radius: 0;
        background: none;
        box-shadow: none;
        color: var(--fg);
        font: 400 11px/1.5 var(--mono);
        text-align: left;
        cursor: pointer;
        white-space: nowrap;
      }

      .row:hover {
        background: var(--panel-2);
      }

      .row[aria-current="true"] {
        background: color-mix(in srgb, var(--select) 16%, transparent);
        box-shadow: inset 2px 0 0 var(--select);
      }

      /* The twisty is a hit area of its own inside the row, so opening a branch and selecting
         it are two different clicks rather than one guess. */
      .twist {
        flex: none;
        width: 13px;
        height: 13px;
        padding: 0;
        border: none;
        background: none;
        box-shadow: none;
        color: var(--fg-faint);
        font-size: 9px;
        line-height: 1;
        cursor: pointer;
      }

      .twist[data-leaf="true"] {
        visibility: hidden;
        cursor: default;
      }

      .name {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .flag {
        flex: none;
        color: var(--danger);
        font-size: 10px;
      }

      .row[data-hidden="true"] .name {
        color: var(--fg-faint);
        font-style: italic;
      }

      /* The eye is a hit area of its own, the same reason the twisty is: hiding a row and
         selecting it are two different clicks. Faint until hovered or actually hiding
         something, so a tree of hundreds of rows does not read as hundreds of eyes. */
      .eye {
        flex: none;
        width: 15px;
        height: 15px;
        padding: 0;
        border: none;
        background: none;
        box-shadow: none;
        color: var(--fg-faint);
        font-size: 10px;
        line-height: 1;
        cursor: pointer;
        opacity: 0;
      }

      .row:hover .eye,
      .row:focus-within .eye,
      .eye[aria-pressed="true"],
      .eye[data-inherited="true"] {
        opacity: 1;
      }

      .eye[aria-pressed="true"] {
        color: var(--danger);
      }

      .eye[data-inherited="true"] {
        color: var(--fg-faint);
        cursor: default;
      }

      .hidden-tag {
        flex: none;
        color: var(--fg-faint);
        font-family: var(--sans);
        font-size: 9px;
      }

      .isolate {
        flex: none;
        padding: 0 2px;
        border: none;
        background: none;
        box-shadow: none;
        color: var(--fg-faint);
        font-family: var(--sans);
        font-size: 9px;
        text-decoration: underline;
        cursor: pointer;
        opacity: 0;
      }

      .row:hover .isolate,
      .row:focus-within .isolate {
        opacity: 1;
      }

      .active {
        margin-left: 6px;
        color: var(--accent);
        font-size: 10px;
      }

      .empty {
        margin: 0;
        padding: 4px 10px;
        font-family: var(--sans);
        font-size: 12px;
        color: var(--fg-dim);
      }

      /* The References group is a sibling of the run's tree, not a branch in it, and reads
         as one: a heading in the sans face, so a file somebody else made does not look like
         a name this run chose. */
      .group {
        padding-bottom: 4px;
        border-bottom: 1px solid var(--line);
        margin-bottom: 4px;
      }

      .group-head {
        margin: 0;
        padding: 4px 10px 2px;
        font-family: var(--sans);
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--fg-faint);
      }
    `,
  ];

  /** Every ref the newest run named. */
  @property({ attribute: false }) refs: readonly string[] = [];

  /** The bodies somebody else made that this project is holding, by file name.
   *
   * Beside `refs` and never inside them: a dropped body was named by no run, and `refs` says
   * in its own line above that it holds what the newest run named. A reference is one row with
   * nothing under it - decision-8's imported mesh "names nothing under it the way a hull does",
   * and decision-7 refused pointing at a survey's own indexing, so there is nothing to nest. */
  @property({ attribute: false }) references: readonly string[] = [];

  /** The one of `references` that is active - the body on the view, and the one `survey`,
   * *detect faces* and the pick panel are about (decision-9, task-49). Choosing a row is what
   * makes it so; the page decides, and marks it here. */
  @property({ attribute: false }) activeReference: string | null = null;

  /** What is selected, wherever it was clicked. */
  @property() selected: string | null = null;

  /** Which reference is selected, if a reference is what is selected. The two never hold at
   * once: the page owns that, the same way it owns `selected`. */
  @property({ attribute: "selected-reference" }) selectedReference: string | null = null;

  /** The refs a check reported, marked on their own row and on the rows above them. */
  @property({ attribute: false }) flagged: readonly string[] = [];

  /** The rows a person has hidden by their eye, by the exact ref path clicked - the page's
   * own set, held here only to draw. "Hides everything under it" is read at draw time, the
   * same way `flagged`'s rows above a finding are: a row is drawn hidden when its own path is
   * in here or a path above it is.
   *
   * Named `hiddenRefs`, not `hidden`: `HTMLElement` already has a `hidden` of its own (shows
   * or hides the whole element), and shadowing it is exactly the kind of thing that reads
   * fine here and breaks the day something calls `element.hidden = true` expecting the DOM's
   * own meaning. */
  @property({ attribute: false }) hiddenRefs: readonly string[] = [];

  /** The branches a person opened by hand. Everything starts shut.
   *
   * This was the other way about, on the reasoning that a run's refs are tens of names rather
   * than a file system. That was measured and it is wrong: `gridfinity_cabinet.py` names 770
   * refs, fourteen of which are parts, because every finger of every joint is a wall with a
   * name. Open by default put hundreds of face rows between the first part and the second.
   * Shut, the container opens as the fourteen parts it was drawn to show. */
  @state() private opened = new Set<string>();

  /** Open whatever is shut above the selection, so a face clicked on the drawing reveals its
   * row rather than landing inside a branch nobody can see.
   *
   * This is the one place a branch opens by itself, and it is why the default may be shut at
   * all: the round-trip does the opening for you. */
  override willUpdate(changed: PropertyValues<this>): void {
    if (!changed.has("selected") || this.selected === null) return;
    const next = new Set(this.opened);
    for (const above of ancestors(this.selected)) next.add(above);
    if (next.size !== this.opened.size) this.opened = next;
  }

  /** And scroll it into view, once the row it needs is actually drawn. */
  override updated(changed: PropertyValues<this>): void {
    if (!changed.has("selected") || this.selected === null) return;
    // By `data-ref`, not by `aria-current` alone: a reference row carries that too, and a
    // ref revealing itself must not scroll to a dropped body that happens to be selected.
    const row = this.shadowRoot?.querySelector(`[data-ref][aria-current="true"]`);
    row?.scrollIntoView({ block: "nearest" });
  }

  override render() {
    const roots = treeOf(this.refs);
    // "This run named nothing yet" is about the run, so it is only the whole answer while
    // there is nothing else here to show. A body dropped before the first run is something.
    if (roots.length === 0 && this.references.length === 0) {
      return html`<p class="empty">This run named nothing yet.</p>`;
    }
    return html`
      ${this.referenceGroup()}
      ${roots.length === 0
        ? html`<p class="empty">This run named nothing yet.</p>`
        : html`<div role="tree">${this.rows(roots).map((row) => this.row(row))}</div>`}
    `;
  }

  /** The dropped bodies, under a heading that says they are not a run's doing. */
  private referenceGroup() {
    if (this.references.length === 0) return nothing;
    return html`
      <div class="group" role="group" aria-labelledby="references-head">
        <p id="references-head" class="group-head">References</p>
        ${this.references.map(
          (file) => html`
            <div
              class="row reference"
              role="button"
              tabindex="0"
              aria-current=${file === this.selectedReference ? "true" : "false"}
              data-reference=${file}
              data-active=${file === this.activeReference ? "true" : "false"}
              @click=${() => this.pickReference(file)}
              @keydown=${(event: KeyboardEvent) => this.keyedReference(event, file)}
            >
              <span class="twist" data-leaf="true" aria-hidden="true"></span>
              <span class="name">${file}</span>
              ${file === this.activeReference ? html`<span class="active">active</span>` : nothing}
            </div>
          `,
        )}
      </div>
    `;
  }

  /** The tree flattened to the rows that are actually on screen, parents before children. */
  private rows(nodes: readonly Node[], depth = 0): Row[] {
    const out: Row[] = [];
    for (const node of nodes) {
      const open = this.opened.has(node.path);
      out.push({ node, depth, open });
      if (open) out.push(...this.rows(node.children, depth + 1));
    }
    return out;
  }

  private row({ node, depth, open }: Row) {
    const leaf = node.children.length === 0;
    const reported = this.flagged.some((one) => within(node.path, one));
    // A row reads hidden either because its own eye is shut or because something above it
    // is - the same "inside" `flagged`'s own marking already reads by, the other way round.
    const selfHidden = this.hiddenRefs.includes(node.path);
    const inherited = !selfHidden && this.hiddenRefs.some((one) => under(node.path, one));
    const effectivelyHidden = selfHidden || inherited;
    const hasHiddenChild =
      !effectivelyHidden && this.hiddenRefs.some((one) => one !== node.path && under(one, node.path));
    return html`
      <div
        class="row"
        role="treeitem"
        tabindex="0"
        aria-current=${node.path === this.selected ? "true" : "false"}
        aria-expanded=${ifDefined(leaf ? undefined : open ? "true" : "false")}
        data-ref=${node.path}
        data-hidden=${effectivelyHidden ? "true" : "false"}
        style=${`padding-left: ${String(4 + depth * 12)}px`}
        @click=${() => this.pick(node.path)}
        @keydown=${(event: KeyboardEvent) => this.keyed(event, node.path)}
      >
        <button
          class="twist"
          type="button"
          data-leaf=${String(leaf)}
          tabindex="-1"
          aria-hidden="true"
          @click=${(event: Event) => this.twist(event, node.path, leaf)}
        >
          ${leaf ? "" : open ? "▾" : "▸"}
        </button>
        <button
          class="eye"
          type="button"
          tabindex="-1"
          aria-hidden="true"
          aria-pressed=${selfHidden ? "true" : "false"}
          data-inherited=${String(inherited)}
          title=${inherited
            ? "hidden - a row above this is hidden"
            : selfHidden
              ? "hidden - click to show"
              : "click to hide"}
          @click=${(event: Event) => this.toggleVisibility(event, node.path, selfHidden)}
        >
          ${effectivelyHidden ? "○" : "◉"}
        </button>
        <span class="name">${node.name}</span>
        ${reported ? html`<span class="flag" title="a check reported this">⚠</span>` : nothing}
        ${effectivelyHidden ? html`<span class="hidden-tag">hidden</span>` : nothing}
        ${hasHiddenChild ? html`<span class="hidden-tag">has hidden</span>` : nothing}
        ${depth === 0
          ? html`
              <button
                class="isolate"
                type="button"
                tabindex="-1"
                aria-hidden="true"
                title="show only this part"
                @click=${(event: Event) => this.isolate(event, node.path)}
              >
                only
              </button>
            `
          : nothing}
      </div>
    `;
  }

  private twist(event: Event, path: string, leaf: boolean): void {
    if (leaf) return;
    // The twisty is inside the row, and opening a branch is not selecting it.
    event.stopPropagation();
    const next = new Set(this.opened);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    this.opened = next;
  }

  /** The eye is inside the row too, and hiding a row is not selecting it - the page owns
   * `hidden` and decides what the new set is; this only ever says which row and which way. */
  private toggleVisibility(event: Event, ref: string, currentlyHidden: boolean): void {
    event.stopPropagation();
    this.dispatchEvent(
      new CustomEvent<RefVisibilityDetail>("ref-visibility", {
        bubbles: true,
        composed: true,
        detail: { ref, hidden: !currentlyHidden },
      }),
    );
  }

  private isolate(event: Event, ref: string): void {
    event.stopPropagation();
    this.dispatchEvent(
      new CustomEvent<RefIsolateDetail>("ref-isolate", { bubbles: true, composed: true, detail: { ref } }),
    );
  }

  private keyed(event: KeyboardEvent, path: string): void {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    this.pick(path);
  }

  private pick(ref: string): void {
    this.dispatchEvent(
      new CustomEvent<RefPickDetail>("ref-pick", { bubbles: true, composed: true, detail: { ref } }),
    );
  }

  private keyedReference(event: KeyboardEvent, file: string): void {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    this.pickReference(file);
  }

  /** As `pick` is: this never selects itself, so the page stays the one owner of what is
   * selected and the two directions cannot fight. */
  private pickReference(file: string): void {
    this.dispatchEvent(
      new CustomEvent<ReferencePickDetail>("reference-pick", {
        bubbles: true,
        composed: true,
        detail: { file },
      }),
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "bench-refs-tree": BenchRefsTree;
  }

  interface HTMLElementEventMap {
    "ref-pick": CustomEvent<RefPickDetail>;
    "reference-pick": CustomEvent<ReferencePickDetail>;
    "ref-visibility": CustomEvent<RefVisibilityDetail>;
    "ref-isolate": CustomEvent<RefIsolateDetail>;
  }
}
