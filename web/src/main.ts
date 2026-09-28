/** The app: a workbench organised by subject (decision-12). The project and its files on the
 * left, the script beside the view in the centre with its output folded under them, the
 * inspector on the right - following whatever is selected - and a status bar under everything.
 * Python runs in a worker.
 *
 * This module is the wiring and the run's state - what is running, what hung, the override
 * table, what is selected and which documents are open - and nothing it can hand to a module of
 * its own. The projects kept and which is open are `files.ts`, their values as the TOML
 * document they are kept and shown as is `values.ts`, what the browser remembers is
 * `storage.ts`, the wording of the status bar and the hints is `status.ts`, the files a run made
 * are `exports.ts`, which subject a selection makes and what a run found on it is
 * `subjects.ts`, the reference mesh on the view and its pick is `reference-body.ts`, the 3D pane
 * that loads on demand is `deferred3d.ts`, and every fact about a scene - counts, panes,
 * placements - arrives from Python already worked out.
 *
 * **The view is a pane, never a tab.** Every other surface here can be covered by something
 * else; the view cannot. Selecting a ref - from the tree, from the editor's cursor, from a
 * click on a face - highlights geometry, and a highlight on a surface that is not on screen is
 * not a feature. So cut sheets open as tabs in the *editor* group, beside the script and its
 * values file, and the view keeps its own part of the centre whatever else is open - given up
 * only when the person asks for the Code layout (`layout.ts`). The
 * survey of a dropped body opens there too, for a different reason: it is a document of a
 * few hundred lines that a maker reads through and comes back to while writing the script
 * that replaces the body, and it outlives every run made while it is open - which is what
 * the panel across the bottom, redrawn by each run at a height for a run's output, is not for.
 *
 * **The values file is the truth and the panel is a view of it.** An edit in the parameters
 * panel is written to the project at once, as every keystroke in the script already is - there
 * is no save anywhere in this app, and a save for the values alone would have made the file
 * truthful only after a click. And what is written is what the run *built*: a number the
 * script's range held at its end comes back from the scene and is written in place of what
 * was sent, so the file never says `units_x = 9` about a cabinet that was built four wide.
 */
import "./styles.css";
import "./components/molecules/layout-switch";
import "./components/molecules/view-modes";
import "./components/organisms/examples-menu";
import "./components/organisms/explorer";
import "./components/organisms/inspector";
import "./components/organisms/lease-chip";
import "./components/organisms/panel";

import { connect } from "./bridge";
import type { BenchLayoutSwitch } from "./components/molecules/layout-switch";
import type { BenchViewModes } from "./components/molecules/view-modes";
import type { BenchExamplesMenu } from "./components/organisms/examples-menu";
import type { BenchExplorer } from "./components/organisms/explorer";
import type { Opening } from "./components/organisms/exports";
import type { BenchInspector } from "./components/organisms/inspector";
import type { BenchLeaseChip } from "./components/organisms/lease-chip";
import type { BenchPanel } from "./components/organisms/panel";
import { treeOf } from "./components/organisms/refs-tree";
import { buttons } from "./components/styles";
import { deferred3d } from "./deferred3d";
import { contentOf, save, zip } from "./downloads";
import * as editor from "./editor";
import { pictured } from "./exports";
import {
  UNTITLED,
  type Project,
  type Workspace,
  adopted,
  created,
  deleted,
  document as projectDocument,
  duplicated,
  merged,
  modulesOf,
  openSource,
  opened,
  pristine,
  renamed,
  restored,
  scriptCopied,
  scriptRemoved,
  scriptRenamed,
  scriptsOf,
  serialized,
  single,
  switched,
  withExample,
  withKept,
  withOverrides,
  withReference,
  withScript,
  withSource,
} from "./files";
import { EXAMPLES, STARTER } from "./generated/pysources";
import { type Overrides, asBuilt, declaredOnly, parsed, withOverride } from "./overrides";
import { referenceBody } from "./reference-body";
import type { OkScene, Scene, SheetView } from "./scene";
import type { SectionAxis, ViewMode } from "./viewer3d";
import { STALE_HINT, STALE_MESSAGE, bundleStale } from "./staleness";
import { built, failing, found, made, noBodiesReason, onBedReason, readOnlyWords } from "./status";
import {
  type Linked,
  PROJECT,
  type Selection,
  type Subject,
  fitLine,
  keptAcross,
  linkOf,
  linked,
  linkedIn,
  subjectOf,
  worstPlace,
} from "./subjects";
// `remember`/`forget` are still here for what belongs to this browser rather than to a
// project - the hang fingerprint, the rail's container, the panel. The projects themselves
// go through `store` (see `store.ts` on what does not travel).
import { type Host, host as hostClient } from "./host";
import { type OutboxState, outbox } from "./outbox";
import { FIRST_LAYOUT, type Layout, layoutOf, nextLayout } from "./layout";
import { type Leasing, identity, leasing } from "./leasing";
import { KEYS, forget, hashOf, remember, remembered } from "./storage";
import type { ProjectStore } from "./store";
import { hostStore } from "./store-host";
import { localStore } from "./store-local";
import { type Level, attach, consoleSink, isLevel, log, timed, userTimingSink } from "./telemetry";
import { BENCH, type ReferenceTable, fromToml, keptOf, placing, stemOf, tomlName } from "./values";

const FIRST = "gridfinity_cabinet.py";
const DEBOUNCE = 300;
const WATCHDOG = 15_000;
const BOOT_TIMEOUT = 60_000;
const ZOOM_STEP = 1.4;

// Every record the page, the worker and Python make comes through `telemetry`: to the console
// at the level `bench.log` in localStorage asks for ("debug" to see everything), and onto the
// User Timing timeline, where the Performance panel draws the spans. A collector - Datadog RUM,
// Grafana Faro, an OpenTelemetry exporter - is one more `attach` beside these two.
attach(consoleSink(levelAsked()));
attach(userTimingSink);

function levelAsked(): Level {
  const said = remembered(KEYS.log);
  return isLevel(said) ? said : "info";
}

/** What to add under any failure: whatever went wrong, the page can always start over. */
const RELOAD_HINT = "If the app does not come back on its own, reload the page.";

// ---- the bits of the page ----------------------------------------------------

const need = <T extends Element>(id: string): T => {
  const found = document.getElementById(id);
  if (found === null) throw new Error(`the page is missing #${id}`);
  return found as unknown as T;
};

const ui = {
  state: need<HTMLSpanElement>("state"),
  status: need<HTMLSpanElement>("status"),
  staleBundle: need<HTMLSpanElement>("stale-bundle"),
  reach: need<HTMLSpanElement>("reach"),
  timing: need<HTMLSpanElement>("timing"),
  openName: need<HTMLSpanElement>("open-name"),
  madeChip: need<HTMLSpanElement>("made"),
  run: need<HTMLButtonElement>("run"),
  stop: need<HTMLButtonElement>("stop"),
  shell: need<HTMLDivElement>("shell"),
  rail: need<HTMLElement>("rail"),
  railFiles: need<HTMLButtonElement>("rail-files"),
  sidebar: need<HTMLElement>("sidebar"),
  explorer: need<BenchExplorer>("explorer"),
  examples: need<BenchExamplesMenu>("examples-menu"),
  inspector: need<BenchInspector>("inspector"),
  findings: need<HTMLButtonElement>("findings"),
  noHost: need<HTMLDivElement>("no-host"),
  noHostWhy: need<HTMLParagraphElement>("no-host-why"),
  adopt: need<HTMLDivElement>("adopt"),
  adoptList: need<HTMLUListElement>("adopt-list"),
  adoptYes: need<HTMLButtonElement>("adopt-yes"),
  adoptNo: need<HTMLButtonElement>("adopt-no"),
  lease: need<BenchLeaseChip>("lease"),
  standing: need<HTMLSpanElement>("standing"),
  layout: need<BenchLayoutSwitch>("layout"),
  groups: need<HTMLDivElement>("groups"),
  editorTabs: need<HTMLDivElement>("editor-tabs"),
  panelScript: need<HTMLDivElement>("panel-script"),
  panelValues: need<HTMLDivElement>("panel-values"),
  valuesText: need<HTMLPreElement>("values-text"),
  panelSheet: need<HTMLDivElement>("panel-sheet"),
  sheetDrawing: need<HTMLImageElement>("sheet-drawing"),
  panelReport: need<HTMLDivElement>("panel-report"),
  reportText: need<HTMLPreElement>("report-text"),
  editor: need<HTMLDivElement>("editor"),
  canvas3d: need<HTMLDivElement>("canvas3d"),
  fit: need<HTMLButtonElement>("fit"),
  zoomIn: need<HTMLButtonElement>("zoom-in"),
  zoomOut: need<HTMLButtonElement>("zoom-out"),
  viewModes: need<BenchViewModes>("view-modes"),
  colourFacesToggle: need<HTMLButtonElement>("colour-faces-toggle"),
  sectionBar: need<HTMLDivElement>("section-bar"),
  sectionAxis: need<HTMLSelectElement>("section-axis"),
  sectionPosition: need<HTMLInputElement>("section-position"),
  panel: need<BenchPanel>("run-panel"),
};

// The page's own markup is not all components yet, and its buttons are the components' own.
if (buttons.styleSheet !== undefined) {
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, buttons.styleSheet];
}

// ---- state -------------------------------------------------------------------

let scene: OkScene | null = null;
let booting = true;
let running = false;
/** Set when this source hung last time and has not been asked for again by hand. */
let held = false;
/** When the run in flight was asked for, so the status bar can say what it cost. */
let asked = 0;

// ---- the projects kept --------------------------------------------------------

/** Where the projects are kept: the host's store, once `chosenStore()` has found the host at
 * the top of `boot()`, and nothing else. Everything below this line moves a document and does
 * not know the place (`store.ts`). `null` until then - and for good on a page with no host
 * behind it, which says so and stops rather than keeping work nowhere (decision-9: "there is no
 * fallback, and that is the decision"). */
let store: ProjectStore | null = null;

/** The route, and the outbox behind `store` - set alongside it and nowhere else. A dropped mesh
 * goes to the host through the outbox without being queued (decision-9), and a placement reads
 * the mesh it names back over the route. */
let client: Host | null = null;
let reach: ReturnType<typeof outbox> | null = null;

/** This tab's write lease on the open project (task-47) - set with `store`, and `null` on a page
 * with no host, which has nothing to lease. */
let lease: Leasing | null = null;

/** Whether this tab may write the open project: it holds the lease on it. Everything that
 * writes asks this first - and while the lease is still being asked for, the answer is no, so
 * nothing is written for a project somebody else turns out to hold. */
function writable(): boolean {
  const standing = lease?.standing() ?? null;
  return standing?.kind === "writer" && standing.project === workspace.current;
}

/** Whether `next` changes a project this tab does not hold - the open one, while it is being
 * read here. The backstop under every writing control being turned off: whatever reaches
 * `keep()` anyway is not kept, because the store writes the whole difference between what it
 * last saw and `next`, and a reader's change left in the workspace would be written by the
 * next unrelated `keep()` - a new project, a switch - rather than never. */
function touchesUnheld(next: Workspace): boolean {
  const standing = lease?.standing() ?? null;
  if (standing === null || standing.kind === "writer") return false;
  const was = workspace.projects.find((one) => one.name === standing.project);
  return was !== undefined && next.projects.find((one) => one.name === standing.project) !== was;
}

/** Whether this page found no host to keep projects on (`showNoHost`) - and so has nothing to
 * run and nothing else to say. */
let hostless = false;

/** How long to wait before asking the host again, while this browser has host work that must
 * not be lost to a store choice made too early - the same shape as the outbox's own backoff. */
const PROBE_START_MS = 1000;
const PROBE_MAX_MS = 30_000;

/** What `chosenStore()` found: the host's store, or - in words a person can act on - why there
 * is no host. */
type Chosen = { readonly store: ProjectStore } | { readonly none: string };

/** Why the route's answer is not a host to keep projects on. A root the host was told about
 * and cannot find says so in the route's own words; anything else that answered is a server
 * without the route - `dist/` behind a plain file server, which decision-9 retired. */
const noHostReason = (refused: { readonly refused: string; readonly message: string }): string =>
  refused.refused === "no-root"
    ? `The host is running, but ${refused.message}.`
    : `This page is being served without bench's projects route (${refused.message}).`;

/** Which store this session uses, decided once: when the host route answers, the host is where
 * the projects are (decision-9), and there is no other answer to fall back on - a route that
 * does not answer is a page with no host, and `boot()` says so rather than keeping work in this
 * browser as if nothing were wrong.
 *
 * *Unless* this browser's own outbox already holds host work: a restart mid-session (decision-9's
 * own words) must not read as "there is no host" and put a person's unreached edits behind a
 * message, so that case waits and retries instead. The browser's own store is not a store here
 * any more: it is read once, to adopt what it held (`offerAdoption`).
 */
async function chosenStore(): Promise<Chosen> {
  // Every request as this tab, so a write carries the lease it is made under (task-47).
  const route = hostClient("", fetch, identity());
  const box = outbox(route);
  // Unreached *writes*, not every row: the outbox keeps a row per file it has ever landed, as
  // a version cache, so "has rows" is true of every browser that has used a host at all and
  // would keep a returning one waiting on a host that has answered - with `no-root`, say -
  // rather than saying so. task-52 read `hasRows()` here, when a browser that had never used
  // the host fell back to its own store; there is no such store to fall back to now.
  const hadWork = (await box.pending()).size > 0;
  let backoffMs = 0;
  for (;;) {
    let listing: Awaited<ReturnType<typeof route.projects>> | null;
    try {
      listing = await route.projects();
    } catch {
      listing = null;
    }
    if (listing !== null && listing.ok) {
      client = route;
      // A host is what opens a file in the slicer, so *Open in slicer* is offered once one is.
      ui.inspector.slicer = true;
      reach = box;
      return { store: hostStore(route, box) };
    }
    if (!hadWork) {
      return {
        none: listing === null ? "Nothing answered at the address this page came from." : noHostReason(listing.refusal),
      };
    }
    log("info", "bench.store", "the host is not answering yet, and this browser has unreached host work", {
      "bench.store.waitedMs": String(backoffMs),
    });
    ui.reach.hidden = false;
    ui.reach.textContent = "waiting for host…";
    ui.reach.title =
      "this browser has work that has not reached the host yet, and the host " +
      (listing === null ? "is not answering" : `answered: ${listing.refusal.message}`);
    ui.reach.dataset.state = "warn";
    backoffMs = backoffMs === 0 ? PROBE_START_MS : Math.min(backoffMs * 2, PROBE_MAX_MS);
    await new Promise<void>((resolve) => {
      const timer = window.setTimeout(resolve, backoffMs);
      const onOnline = (): void => {
        window.clearTimeout(timer);
        window.removeEventListener("online", onOnline);
        resolve();
      };
      window.addEventListener("online", onOnline);
    });
  }
}

/** A page with no host behind it: said in words, at the top of the editor group and on the
 * status bar, and everything that would look as if it could keep something is put out of
 * reach - an editor that took typing and a Run that ran it would be a bench appearing to work
 * with nowhere to put the work (task-46 AC#5). */
function showNoHost(why: string): void {
  hostless = true;
  log("warn", "bench.store", "there is no host behind this page", { "bench.store.problem": why });
  ui.noHost.hidden = false;
  ui.noHostWhy.textContent = why;
  setState("error", "no host - nothing here can be opened or kept", true);
  // The inspector says it too, rather than showing a project that is not there.
  ui.inspector.error = `There is no host behind this page. ${why}`;
  ui.reach.hidden = false;
  ui.reach.textContent = "no host";
  ui.reach.title = why;
  ui.reach.dataset.state = "error";
  for (const away of [ui.rail, ui.sidebar, ui.examples, ui.editorTabs, ui.panelScript]) {
    away.inert = true;
  }
  ui.run.disabled = true;
}

/** What the reach indicator says for `state`, which colour it reads as, and the longer sentence
 * that goes in its `title` rather than its text - `.state` does not grow with what it says
 * (`styles.css`), so a refusal's own message lives in a tooltip instead of pushing the status
 * bar around. `status.ts`'s own kind of function, but kept here beside the outbox it describes
 * rather than pulled apart from it. Every state is named in words, never a bare dot (task-54). */
function reachWords(state: OutboxState): { text: string; title: string; kind: "ok" | "boot" | "warn" | "error" } {
  switch (state.kind) {
    case "clear":
      return { text: "saved to host", title: "every edit has reached the host", kind: "ok" };
    case "sending":
      return { text: "saving to host…", title: "an edit is on its way to the host", kind: "boot" };
    case "waiting":
      return {
        text: "not yet reached host",
        title: "the host is not answering; this will be sent again once it is",
        kind: "warn",
      };
    case "refused": {
      const file = state.file.split("/").slice(1).join("/");
      return { text: `${file} refused`, title: `the host refused this write: ${state.message}`, kind: "error" };
    }
  }
}

/** Whether the reach chip is away because this tab is only reading (`showReach`). */
let reachPutAway = false;

function showReach(state: OutboxState): void {
  const { text, title, kind } = reachWords(state);
  // A reader keeps nothing, so "saved to host" would be about nothing it did: the chip is put
  // away while reading - unless it is saying that something this tab wrote before it lost the
  // lease has not landed, which is still true and still worth knowing.
  const standing = lease?.standing() ?? null;
  const reading = standing?.kind === "reader" && standing.project === workspace.current;
  reachPutAway = reading && (state.kind === "clear" || state.kind === "sending");
  if (reachPutAway) {
    ui.reach.hidden = true;
    return;
  }
  ui.reach.hidden = false;
  ui.reach.textContent = text;
  ui.reach.title = title;
  ui.reach.dataset.state = kind;
}

/** Every project kept, and the open one.
 *
 * Starts as the workspace a host with nothing on it would have, and is replaced by what the
 * store answers with in `boot()`. It is never *unset*: a store that has to be asked is no
 * reason for the rest of this file to hold a `Workspace | null` and check it everywhere.
 */
let workspace: Workspace = firstWorkspace();

/** Whether `workspace` is still `firstWorkspace()` as it was made - a host with nothing on it,
 * showing the first example, and nobody has changed anything yet. Nothing is written for it
 * until somebody does: a page loading is not a reason to make a directory on somebody's disk,
 * and a browser about to be asked whether to adopt its own projects should not find an
 * untouched example already sitting on the host in their way. */
let fresh = false;

/** A host with no projects yet: the first example, as a project of its own, not yet written. */
function firstWorkspace(): Workspace {
  return single(stemOf(FIRST), EXAMPLES[FIRST] ?? "");
}

/** `space` opened where this browser left it: the project and the script it last had open, when
 * both are still there - or the store's own first project, at its entry, when not. Which
 * project is open is this browser's alone (`files.ts`), so it comes from here and never from
 * the host. */
function reopened(space: Workspace): Workspace {
  let said: unknown;
  try {
    said = JSON.parse(remembered(KEYS.open) ?? "null");
  } catch {
    said = null;
  }
  if (typeof said !== "object" || said === null) return space;
  const { project, script } = said as { project?: unknown; script?: unknown };
  if (typeof project !== "string") return space;
  const there = switched(space, project);
  if (there.current !== project) return space;
  return typeof script === "string" ? withScript(there, script) : there;
}

/** Make `next` the workspace: the host keeps it, and the title bar, the explorer and the values
 * tab show it. */
function keep(next: Workspace): void {
  if (touchesUnheld(next)) {
    log("warn", "bench.lease", "a change to a project this tab does not hold was not kept", {
      "bench.project": workspace.current,
    });
    return;
  }
  fresh = false;
  show(next);
  // Deliberately not awaited. Every keystroke and every knob turn comes through here, and a
  // person editing a script must not be made to wait on a write - decision-9's outbox rule,
  // which is why `keep` stayed synchronous when the store became asynchronous. A write that
  // fails says so; it does not take the edit down with it.
  const kept = store;
  if (kept === null) return;
  void kept.save(serialized(next)).catch((problem: unknown) => {
    log("error", "bench.store", "the projects were not kept", {
      "bench.store.kind": kept.kind,
      "bench.store.problem": String(problem),
    });
  });
}

/** Put `next` on screen as the workspace without keeping it anywhere - what a store has just
 * answered with needs no writing back, and a fresh host's first example is not written until
 * somebody changes it. Which project and script are open is remembered here, in this browser. */
function show(next: Workspace): void {
  workspace = next;
  remember(KEYS.open, JSON.stringify({ project: next.current, script: next.script }));
  ui.openName.textContent = next.current;
  showFiles();
  // The meshes are the directory's, not the store's: asked for again when the project changes.
  if (meshesOf !== next.current && client !== null) void readMeshes();
  showValues();
  drawTabs();
  // A different project may place the very body already dropped, or stop placing the one
  // that was - so the body's tools are said again for whichever project is open now, since
  // what they will let a maker do depends on that very answer.
  body.refresh();
  showAdoption();
  // The lease follows the open project: a different one is let go of and this one asked for.
  lease?.open(next.current);
  showStanding();
}

// ---- the write lease: who may write the open project -----------------------------------

/** Say where this tab stands on the open project, everywhere it changes what a person can do:
 * the header's chip with whose it is, the status bar, the editor taking typing or not,
 * the knobs' own container, and every control that would write. */
function showStanding(): void {
  const standing = lease?.standing() ?? null;
  const reading = standing?.kind === "reader" && standing.project === workspace.current ? standing : null;
  const can = writable();
  code.setReadOnly(!can);
  ui.editor.dataset["readonly"] = String(!can);
  ui.explorer.readOnly = reading !== null;
  ui.inspector.reading = reading !== null;
  showSelected();
  body.refresh();
  if (reading === null) {
    ui.lease.words = null;
    ui.lease.lost = false;
    ui.standing.hidden = true;
    if (reach !== null && reachPutAway) showReach(reach.state());
    return;
  }
  const words = readOnlyWords(reading.project, reading.holder, reading.lost);
  ui.lease.words = words;
  ui.lease.lost = reading.lost;
  ui.standing.hidden = false;
  if (reach !== null) showReach(reach.state());
  ui.standing.textContent = words.chip;
  ui.standing.title = words.chipTitle;
}

/** The lease came back to this tab after somebody else had it: what is on the host now is read
 * again before anything is written, so the store's own idea of what it last saw - and the
 * outbox's bases - are the host's rather than what this tab read before the other writer
 * started. Knob values turned while reading were never kept, and go with it. */
async function regained(project: string): Promise<void> {
  if (store === null) return;
  await reach?.retryLeased(project);
  let read: Workspace | null;
  try {
    read = restored(await store.load());
  } catch (problem: unknown) {
    log("warn", "bench.lease", "the project could not be read again on taking its lease", {
      "bench.store.problem": String(problem),
    });
    return;
  }
  if (read === null || workspace.current !== project) return;
  const there = switched(read, project);
  if (there.current !== project) return;
  const next = withScript(there, workspace.script);
  show(next);
  showOverrides(opened(next).overrides);
  code.replace(openSource(next));
  window.clearTimeout(timer);
  runNow();
  log("info", "bench.lease", "this tab holds the lease again, and read the project afresh", {
    "bench.project": project,
  });
}

/** What the tab last stood as, so a change can be told from a renewal. */
let stood: ReturnType<Leasing["standing"]> = null;

function standingChanged(): void {
  const now = lease?.standing() ?? null;
  const was = stood;
  stood = now;
  if (now?.kind === "writer" && was?.kind === "reader" && was.project === now.project) {
    void regained(now.project);
  }
  showStanding();
}

ui.lease.addEventListener("lease-take-over", () => {
  log("warn", "bench.lease", "this tab took over a project somebody else was writing", {
    "bench.project": workspace.current,
  });
  void lease?.takeOver();
});

// Let go on the way out, so the next client has it at once - a courtesy the expiry backs up,
// since a page may be thrown away without this running at all (decision-9).
window.addEventListener("pagehide", () => {
  lease?.release();
});
// A page brought back from the back-forward cache let go on its way into it.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) lease?.resume();
});

/** A project's values as the file they are - the one thing the values tab shows and the
 * download carries. The lines follow the script's own declaration order once a run has said
 * it, so the file reads like the dataclass does. */
const valuesDocument = (one: Project): string => projectDocument(one, scene?.params.map((param) => param.name) ?? []);

/** Put the open project's values file on its tab - and, when it could not be read, say so
 * above it and on the tab: the panel is then on the script's defaults, and what is turned
 * there is not kept, because keeping it would mean writing over the file (`Kept.unreadable`). */
function showValues(): void {
  const one = opened(workspace);
  const unreadable = one.kept.unreadable;
  ui.valuesText.textContent =
    unreadable === undefined
      ? valuesDocument(one)
      : `# bench could not read this file (${unreadable.problem}), so the panel is on the\n` +
        "# script's own defaults and nothing turned there is written here. Put the line right\n" +
        `# and reload.\n\n${unreadable.text}`;
}

// ---- adopting what this browser kept ----------------------------------------------

/** The projects this browser kept before projects lived on the host, waiting on the person's
 * answer - empty once it is given, and whenever there was nothing to ask about. */
let adopting: readonly Project[] = [];

/** What this browser kept that is worth asking about: every project in its own store - or,
 * from before there were files at all, the one script it kept - that is not simply an example
 * exactly as it shipped, which the app used to open for everybody and nobody would want carried
 * anywhere. Nothing once the question has been answered either way: it is asked once. */
async function adoptable(): Promise<readonly Project[]> {
  if (remembered(KEYS.adopted) !== null) return [];
  let kept: Workspace | null;
  try {
    kept = restored(await localStore().load());
  } catch {
    kept = null;
  }
  const source = remembered(KEYS.source);
  const found =
    kept ?? (source === null ? null : adopted(source, parsed(remembered(KEYS.overrides)), EXAMPLES, FIRST));
  return (found?.projects ?? []).filter((one) => !pristine(one, EXAMPLES));
}

/** The root the question names its directories under - the host's own answer. */
let adoptingRoot = "";

/** The directories adopting would create, named in full, as they would be *now*: said again
 * whenever the workspace changes while the question waits (`show`), since a project made or
 * an example first written in the meantime can take a name the list had promised. */
function showAdoption(): void {
  if (adopting.length === 0) return;
  const into = adoptedInto(adopting);
  const names = into === null ? [] : into.projects.slice(-adopting.length).map((one) => one.name);
  ui.adoptList.replaceChildren(
    ...names.map((name) => {
      const row = document.createElement("li");
      row.textContent = `${adoptingRoot}/${name}/`;
      return row;
    }),
  );
}

/** Where adopting would put `incoming`, beside what is on the host now: the fresh first example
 * is not on the host and is not kept beside them. */
const adoptedInto = (incoming: readonly Project[]): Workspace | null => merged(fresh ? null : workspace, incoming);

/** Ask, once, whether to write this browser's own projects onto the host - naming every
 * directory it would create under the host's root before anything is written (decision-9:
 * "adopting what is in `localStorage` writes real files onto a real disk. It asks first, naming
 * the directory it is about to create. It does not happen because the page loaded.") */
async function offerAdoption(): Promise<void> {
  const incoming = await adoptable();
  if (incoming.length === 0 || client === null) return;
  const listed = await client.projects().catch(() => null);
  adoptingRoot = listed?.ok === true ? listed.value.root.replace(/[/\\]+$/, "") : "the host's projects root";
  adopting = incoming;
  showAdoption();
  ui.adopt.hidden = false;
  log("info", "bench.adopt", "this browser holds projects from before; asking before writing them", {
    "bench.adopt.count": String(incoming.length),
  });
}

ui.adoptYes.addEventListener("click", () => {
  const into = adoptedInto(adopting);
  const count = adopting.length;
  adopting = [];
  ui.adopt.hidden = true;
  remember(KEYS.adopted, "adopted");
  if (into === null) return;
  log("info", "bench.adopt", "this browser's projects were written to the host", {
    "bench.adopt.count": String(count),
  });
  load(into);
});

ui.adoptNo.addEventListener("click", () => {
  adopting = [];
  ui.adopt.hidden = true;
  remember(KEYS.adopted, "declined");
  log("info", "bench.adopt", "this browser's projects were left where they were");
});

function setState(state: "boot" | "running" | "ok" | "error", text: string, bad = false): void {
  ui.state.dataset["state"] = state;
  ui.state.textContent = state === "boot" ? "booting" : state;
  ui.status.textContent = text;
  ui.status.classList.toggle("is-error", bad);
}

/** Say again what the app is doing, from what it knows - used when "ready" arrives, which
 * is the moment the boot messages stop being the most useful thing on the line. */
function repaint(): void {
  if (running) {
    setState("running", "running…");
    return;
  }
  if (held) {
    setState("error", "this script was stopped last time; press Run to try it again", true);
    return;
  }
  if (scene !== null) {
    setState("ok", built(scene.summary), failing(scene.summary));
    return;
  }
  setState("ok", "ready");
}

/** Put a failure in front of somebody: the inspector says it at its top, whatever it is
 * showing, since a failure is about the run rather than about any part of it. */
function showFailure(message: string): void {
  ui.inspector.error = `${message}\n\n${RELOAD_HINT}`;
}

// ---- the three pieces --------------------------------------------------------

/** The view. A click in it is the selection - the inspector's subject - so `Mod-I` inserts the
 * ref it names and the tree reveals the row; a click on nothing is nothing selected, which is
 * the project. The editor's cursor lights up what it is pointing at. */
const space = deferred3d(ui.canvas3d, {
  onSelect(ref) {
    // A redraw puts down a ref the view no longer draws, and says so - but what stays selected
    // across a run is `keptAcross`'s to decide, from everything the run named, not the view's.
    if (redrawing) return;
    showSelection(ref);
  },
  onSelectSecond(ref) {
    showSecondSelection(ref);
  },
  onDetectPick(hit) {
    body.picked(hit);
  },
});

/** A body somebody else made, dropped on the view - held, surveyed, detected and placed by
 * `reference-body.ts`, whose tools the inspector shows while the body is its subject. What is
 * left here is what touches the project: its directory on the host, and its `[reference]`. */
const body = referenceBody({
  detectOnView(flatIndex) {
    space.detect(flatIndex);
  },
  survey(reference, table) {
    bridge.survey(reference, table);
  },
  detect(reference, table) {
    bridge.detect(reference, table);
  },
  runNow() {
    runNow();
  },
  placement: () => opened(workspace).reference,
  place(table) {
    keep(withReference(workspace, table));
  },
  writable,
  openReport() {
    openReport();
  },
  closeReport() {
    closeReport();
  },
  changed() {
    ui.inspector.tools = body.view();
  },
});

/** `modulesOf(workspace)`, as the JSON text the worker takes - `undefined` for a project of
 * one script, which is most of them, so a run with nothing beside the open script mounts
 * nothing (task-50). */
const modulesJson = (): string | undefined => {
  const modules = modulesOf(workspace);
  return Object.keys(modules).length === 0 ? undefined : JSON.stringify(modules);
};

/** The references as the project's inspector lists them: every mesh the open project holds,
 * and the body on the view when it is not one of them (a drop a reader made, or one the host
 * would not take) - with the one on the view marked active, since that is the one everything
 * that measures is about (task-49). */
function showReferenceRows(): void {
  const held = meshesOf === workspace.current ? meshes : [];
  const name = body.name();
  ui.inspector.references = name === "" || held.includes(name) ? held : [...held, name];
  ui.inspector.activeReference = name === "" ? null : name;
  ui.inspector.tools = body.view();
}

/** Make `file`, one of the open project's meshes, the active reference in its `[reference]`
 * table - one table naming the active mesh, decision-4's grammar (task-49) - so a reload, and
 * `tools.build`, bring back the same one. A reader chooses on its own view and writes nothing.
 *
 * A table that *placed* another mesh is replaced by one that names this one and places nothing
 * yet: `[reference]` has room for one body, and the placement was of the other. Said, beside the
 * body's tools, rather than done quietly. */
function activate(file: string): void {
  const table = opened(workspace).reference;
  if (table?.["file"] === file || !writable()) return;
  const was = table?.["file"];
  const placed = table !== null && placing(table) && typeof was === "string";
  keep(withReference(workspace, { file }));
  body.choseSaying(
    placed ? `[reference] names ${file} now, placed nowhere yet: the placement it held was of ${was}, and went with it.` : "",
  );
  log("info", "bench.reference", "a reference was made the active one", {
    "bench.reference.name": file,
    "bench.project": workspace.current,
  });
}

/** Put the open project's mesh `file` on the view and make it the active reference - read from
 * the project's directory, surveyed, run against - and the inspector's subject. `quietly` keeps
 * its report behind its button, for a row chosen in the inspector rather than a file opened from
 * the tree. */
async function chooseReference(file: string, quietly: boolean): Promise<void> {
  const project = workspace.current;
  const got = await client?.read(project, file).catch(() => null);
  if (got === undefined || got === null || !got.ok) {
    showFailure(`${file} could not be read from ${project}${got?.ok === false ? `: ${got.refusal.message}` : ""}.`);
    return;
  }
  if (workspace.current !== project) return; // another project opened while this was read
  hold(file, got.value.bytes, quietly);
  activate(file);
  showReferenceSelection(file);
}

/** Make `bytes`, called `name`, the body on the view (`reference-body.ts`). A drop replaces what
 * was there, so a selection on the body that has just gone would name a row nothing holds: it is
 * cleared before the new rows go down, not after. */
function hold(name: string, bytes: Uint8Array, quietly: boolean): void {
  body.hold(name, bytes, quietly);
  if (subject.kind === "reference") showSelection(null);
  showReferenceRows();
}

/** Take the body off the view. The row it was selected on has gone, so the selection goes with
 * it rather than pointing at a body nothing is holding any more. */
function forgetBody(): void {
  body.forget();
  if (subject.kind === "reference") showSelection(null);
  showReferenceRows();
}

// Both of these, not just `dragover`: a real drag from the desktop only delivers `drop` to
// an element that answered `dragenter` as well, and cancelling one without the other is why
// a synthetic drop can work in a test while a person's drag quietly does nothing at all.
for (const stage of ["dragenter", "dragover"] as const) {
  ui.canvas3d.addEventListener(stage, (event: DragEvent) => {
    if (event.dataTransfer === null) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
}

// And a guard over the whole window, because the default for a file dropped anywhere else is
// to navigate to it - which throws away the editor, the open file and the run, and is a
// miserable thing to happen to somebody who missed the view by a few pixels.
for (const stage of ["dragover", "drop"] as const) {
  window.addEventListener(stage, (event: DragEvent) => {
    if (event.defaultPrevented) return;
    event.preventDefault();
  });
}

/** Whether two files hold the same bytes. */
function sameBytes(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let at = 0; at < a.length; at += 1) if (a[at] !== b[at]) return false;
  return true;
}

/** Write a dropped body into `project`'s own directory (task-46 AC#7), so the `[reference]`
 * table that places it names a file the project holds rather than one a browser happened to
 * have on its view - and a reload, `tools.build` and the maker's own editor all find it there.
 *
 * Straight through, never queued: a mesh is never edited, so there is nothing to coalesce and
 * nothing to survive a reload for (decision-9) - it lands now or says it did not. The same file
 * dropped again is already there and nothing more is written. A *different* file of the same
 * name is not written over: the drop only ever creates, and the body's tools say it is not kept
 * rather than a stale-looking success, because the project's copy may be one a placement was
 * measured against. */
async function keepBody(project: string, name: string, bytes: Uint8Array): Promise<boolean> {
  if (reach === null || client === null) return false;
  let problem: string;
  try {
    const sent = await reach.sendThrough(project, name, bytes);
    if (sent.ok) {
      log("info", "bench.reference", "the dropped body was written into the project", {
        "bench.reference.name": name,
        "bench.project": project,
      });
      if (workspace.current === project) await readMeshes();
      return true;
    }
    if (sent.refusal.refused === "exists") {
      const there = await client.read(project, name);
      if (there.ok && sameBytes(there.value.bytes, bytes)) return true;
      problem = `${project} already holds a different ${name}, and a drop does not write over it`;
    } else {
      problem = sent.refusal.message;
    }
  } catch (thrown: unknown) {
    problem = `the host could not be reached (${String(thrown)})`;
  }
  log("warn", "bench.reference", "the dropped body was not written into the project", {
    "bench.reference.name": name,
    "bench.project": project,
    "bench.store.problem": problem,
  });
  if (body.name() !== name) return false; // replaced on the view while this was being refused
  body.notKept(problem);
  return false;
}

/** Put back on the view the body the open project's `[reference]` names, read from the
 * project's own directory - the placement and the body it places now survive a reload
 * together, which is what writing the drop into the project was for. Nothing when the table
 * names nothing, names the body already on the view, or names a file the directory does not
 * hold (decision-4's rule still stands: nothing is placed that is not there). Quietly: the
 * inspector stays on what it was showing, and the body is a row of the project's references. */
async function heldBody(): Promise<void> {
  const one = opened(workspace);
  const file = one.reference?.["file"];
  if (typeof file !== "string" || file === body.name() || client === null) return;
  const got = await client.read(one.name, file).catch(() => null);
  if (got === null || !got.ok) return;
  if (workspace.current !== one.name) return; // the person has opened something else since
  hold(file, got.value.bytes, true);
}

ui.canvas3d.addEventListener("drop", (event: DragEvent) => {
  const file = event.dataTransfer?.files[0];
  if (file === undefined) return;
  event.preventDefault();
  // A drop is somebody's work arriving in a project, so a fresh host's first example is
  // written now rather than holding a mesh in a directory with no script beside it.
  const keeping = writable();
  if (fresh && keeping) keep(workspace);
  const project = workspace.current;
  void (async () => {
    const bytes = new Uint8Array(await file.arrayBuffer());
    hold(file.name, bytes, false);
    // A drop is the maker asking about the body, so the body is what the inspector shows.
    showReferenceSelection(file.name);
    if (keeping) {
      // Kept beside the others, never over them, and made the active one (task-49): a second
      // drop adds a row rather than replacing the first.
      if ((await keepBody(project, file.name, bytes)) && workspace.current === project) activate(file.name);
      return;
    }
    // Read-only here: the body is on the view to be measured, and is not put in a project
    // somebody else is writing (task-47).
    body.notKept(`${project} is open read-only here`);
  })();
});

// The body's tools ask; the body and the project are changed here.
ui.inspector.addEventListener("reference-survey", () => {
  if (body.report() !== null) openReport();
});
ui.inspector.addEventListener("reference-detect", () => {
  body.toggleDetect();
});
ui.inspector.addEventListener("reference-remove", () => {
  forgetBody();
});
ui.inspector.addEventListener("pick-assign", (event) => {
  body.assign(event.detail.how);
});
ui.inspector.addEventListener("pick-field", (event) => {
  body.typed(event.detail.field, event.detail.text);
});
ui.inspector.addEventListener("pick-write", () => {
  body.write();
});
ui.inspector.addEventListener("pick-unplace", () => {
  body.unplace();
});

let timer: number | undefined;

/** The one override table there is. The panel is handed it and never keeps a copy; an edit
 * comes back up as `param-change`, and a scene arriving mid-debounce has no table to put
 * back. */
let overrides: Overrides = {};

/** The table the latest request was sent with. A scene answers the latest request (the
 * bridge drops superseded ones), so while this is still `overrides` the scene's values are
 * the truth about that very table - and an edit made since, still waiting out its debounce,
 * makes it a table the scene knows nothing about, which is left alone. */
let sentWith: Overrides = overrides;

/** Replace the table: what the panel shows, what the open project remembers, and whether
 * there is anything to reset.
 *
 * A reader's table is the run's and nobody else's (task-47, decision-9's "knobs are the
 * interesting middle"): it turns, it runs, and it never reaches the workspace - not merely
 * never reaches the host - because the store writes whatever the workspace holds the next time
 * anything is kept. */
function setOverrides(next: Overrides): void {
  showOverrides(next);
  if (writable()) keep(withOverrides(workspace, next));
}

/** The table on screen and in hand, without keeping it - what a store has just answered with. */
function showOverrides(next: Overrides): void {
  overrides = next;
  ui.inspector.overrides = next;
}

// Mounted empty: what is in it comes from the store, which has to be asked. `boot()` puts
// the open project's script in before anything runs.
const code = editor.mount(ui.editor, "", {
  onChange() {
    // `replace` reports itself as a change; the same text put back is not an edit, and keeping
    // it would write a fresh host's untouched first example on the way in (`fresh`).
    if (code.text() === openSource(workspace)) return;
    // The editor takes no typing while reading (`showStanding`); this is for anything that
    // puts text in by other means, which is not kept either.
    if (!writable()) return;
    keep(withSource(workspace, code.text()));
    window.clearTimeout(timer);
    timer = window.setTimeout(runNow, DEBOUNCE);
  },
  onCursorRef(ref) {
    space.point(ref);
  },
  onRun() {
    window.clearTimeout(timer);
    runNow();
  },
  onInsert() {
    insertSelected();
  },
});

const bridge = connect(
  {
    onStatus(text) {
      // A page with no host has said so on this line, and Python coming up behind it is not
      // news worth painting over that with.
      if (hostless) return;
      if (text === "ready") {
        booting = false;
        repaint();
        return;
      }
      // Anything else is boot progress. A fresh worker after a stop boots again, in the
      // background, and that must not paint over the news of why it was replaced: the line
      // is only given to the boot while something is actually waiting on it.
      booting = true;
      if (running || (scene === null && !held)) setState("boot", text);
    },
    onScene(next) {
      received(next);
    },
    onFailure(message) {
      booting = false;
      running = false;
      ui.stop.disabled = true;
      setState("error", message, true);
      showFailure(message);
    },
    onRunaway(message) {
      // This source is a known runaway now: a reload must not replay it by itself.
      remember(KEYS.hang, hashOf(code.text()));
      held = true;
      booting = false;
      running = false;
      ui.stop.disabled = true;
      setState("error", message, true);
      showFailure(`${message}. Press Run to try it again, or edit it first.`);
    },
    onBusy(busy) {
      running = busy;
      ui.stop.disabled = !busy;
    },
    onSurvey(outcome) {
      body.surveyed(outcome);
    },
    onDetect(outcome) {
      body.detected(outcome);
    },
  },
  { watchdog: WATCHDOG, bootTimeout: BOOT_TIMEOUT },
);

// ---- running -----------------------------------------------------------------

function runNow(): void {
  // Nothing runs on a page with no host - `Ctrl/Cmd+Enter` reaches here past the inert
  // controls, and "running…" over the no-host line would be a bench appearing to work.
  if (hostless) return;
  held = false;
  asked = performance.now();
  forget(KEYS.hang);
  // While Python is still coming up, the boot status is the more useful thing to say.
  if (booting) setState("boot", ui.status.textContent ?? "starting…");
  else setState("running", "running…");
  sentWith = overrides;
  bridge.request(code.text(), overrides, body.reference() ?? undefined, body.tableJson(), modulesJson());
}

function received(next: Scene): void {
  booting = false;
  ui.timing.textContent = `${((performance.now() - asked) / 1000).toFixed(1)} s`;
  if (!next.ok) {
    code.showError(next.error.line);
    flagScript(next.error.line);
    setState("error", next.error.message, true);
    // At the top of the inspector, whatever it is showing: the last run's parts stay under it,
    // as the view keeps drawing them, until a run that works replaces them.
    ui.inspector.error =
      next.error.traceback.trim() === ""
        ? next.error.message
        : `${next.error.message}\n\n${next.error.traceback.trim()}`;
    showStreams(next);
    // A run that failed checked nothing, so the last run's count would be about another script.
    showFindings(null);
    return;
  }
  scene = next;
  // A run that got all the way here is not the thing that hung.
  forget(KEYS.hang);
  held = false;
  // The table is pruned to what the script declares, and - when it is still the table this
  // run was asked with - each value is replaced by what the run built from it, so the file
  // says what was made. Either way the same table comes back when nothing changed.
  const declared = declaredOnly(overrides, next.params);
  const settled = overrides === sentWith ? asBuilt(declared, next.values) : declared;
  if (settled !== overrides) setOverrides(settled);
  else showValues(); // the file follows the script's order, which this run has just said
  // A run can succeed and still be wrong: a check that found an ERROR marks its line in the
  // editor exactly as a raised exception would, because a part that will not work is not a
  // detail in a list.
  code.showError(next.summary.error_line);
  flagScript(next.summary.error_line);
  code.knowRefs(next.refs);
  ui.inspector.error = "";

  // What stays selected is worked out from the run before the view is redrawn, since the redraw
  // drops a lit ref the view no longer draws and would otherwise put the part down with it.
  const kept = keptAcross({ subject, lit: picked }, next.parts, next.refs);
  redrawing = true;
  try {
    timed("bench.view.geometry", () => showGeometry(next), { "bench.parts": next.summary.parts });
  } finally {
    redrawing = false;
  }
  // Forget a hidden row the newest run no longer names, so "show all" is never left disabled
  // over a ref that could not come back anyway, and the eye state never grows across runs
  // beyond what the tree can actually show.
  if (hiddenRefs.size > 0) {
    const known = new Set(next.refs);
    const kept = new Set([...hiddenRefs].filter((ref) => known.has(ref)));
    if (kept.size !== hiddenRefs.size) hiddenRefs = kept;
  }
  applyHidden();
  const inspector = ui.inspector;
  inspector.params = next.params;
  inspector.parts = next.parts;
  inspector.bed = next.bed;
  inspector.refs = next.refs;
  inspector.violations = next.violations;
  inspector.warnings = next.warnings;
  inspector.sheets = next.sheets;
  inspector.files = next.files;
  // What the slicer said was about the files of the run before, or of another project's.
  inspector.opening = {};
  // A part or face the newest run still names stays the subject; one it does not is the
  // project (task-92). A link the page was opened on is followed once there is a run to find it
  // in, and wins over whatever was selected before it arrived.
  if (linking) followLink(next);
  else keepSelection(kept);
  showStreams(next);
  showFindings(next);
  keepSheetTabs(next.sheets);
  ui.madeChip.textContent = made(next.summary);
  // The status bar is the one place the count is said in words.
  setState("ok", built(next.summary), failing(next.summary));
}

/** The status bar's count of what the checks found, as a way to the part worst off - hidden
 * while nothing was found. */
function showFindings(ok: OkScene | null): void {
  const said = ok === null ? "" : found(ok.summary);
  ui.findings.hidden = said === "";
  ui.findings.textContent = said;
  ui.findings.dataset["state"] = ok !== null && failing(ok.summary) ? "error" : "warn";
}

// The count goes to the part that is worst off, with the first place of its worst finding lit -
// or, when what was found is on no one part, to the project, which lists it.
ui.findings.addEventListener("click", () => {
  const worst = scene === null ? null : worstPlace(scene.parts, scene.violations);
  if (worst === null) {
    space.select(null);
    showSelection(null);
    return;
  }
  showSelection(worst.part);
  showPlace(worst.place);
});

/** Draw the scene: every part with a body, standing where the stage put it, and why the view
 * is empty when none has one. */
function showGeometry(ok: OkScene): void {
  // The overhang findings' places are what *On bed* paints: picked out of the run's findings
  // by the check that made them, never worked out here.
  const overhangs = ok.violations.filter((one) => one.check === "overhangs").flatMap((one) => one.refs);
  space.show(ok.parts, ok.stage, ok.sheets, ok.reference, ok.context, ok.bed, overhangs);
  sayWhyEmpty(ok);
  // Not `space.section(...)` again - the view keeps a section exactly as set across a
  // redraw, which is the whole point (task-62). Only the range the slider offers is worth
  // keeping current, and only for the axis actually chosen, so a later toggle-on or axis
  // change starts from where the work now stands rather than where it stood when the page
  // opened.
  stageBounds = ok.stage.bounds;
}

/** The last run's `stage.bounds` - `x0, y0, z0, x1, y1, z1` - kept so the section slider's
 * range can be worked out without asking the viewer for it. */
let stageBounds: readonly number[] = [-50, -50, 0, 50, 50, 50];

/** Where `axis` runs in the last drawn stage, `[low, high]`. */
function sectionRange(axis: SectionAxis): readonly [number, number] {
  const at = axis === "x" ? 0 : axis === "y" ? 1 : 2;
  const [low = -50, high = 50] = [stageBounds[at], stageBounds[at + 3]];
  return [low, high];
}

/** The way of looking at the view (decision-12) - kept here, like the section, so a re-run or
 * a knob change leaves it exactly as it was. */
let viewMode: ViewMode = "assembled";
let sectionAxis: SectionAxis = "x";
let sectionPosition = 0;

/** Why the view has nothing in it, for the way it is being looked at - `""` when it has. */
function sayWhyEmpty(ok: OkScene | null): void {
  if (ok === null) return;
  space.say(viewMode === "bed" ? onBedReason(ok.summary, ok.bed) : noBodiesReason(ok.summary));
}

/** Put the slider's own range and handle at the middle of `axis`'s current span - called
 * only when the axis is chosen anew (turning the section on, or picking a different axis),
 * never on a redraw, which is what keeps the plane still while a knob sweeps geometry
 * through it. */
function centreSectionOn(axis: SectionAxis): void {
  const [low, high] = sectionRange(axis);
  ui.sectionPosition.min = String(low);
  ui.sectionPosition.max = String(high);
  ui.sectionPosition.step = String(Math.max((high - low) / 200, 0.001));
  sectionPosition = (low + high) / 2;
  ui.sectionPosition.value = String(sectionPosition);
}

/** Where the section cuts. The plane is always kept; the view clips at it only in *Section*,
 * and the controls that move it are there and live only then. */
function applySection(): void {
  const cutting = viewMode === "section";
  ui.sectionBar.hidden = !cutting;
  ui.sectionAxis.disabled = !cutting;
  ui.sectionPosition.disabled = !cutting;
  space.section({ axis: sectionAxis, position: sectionPosition });
}

function applyMode(next: ViewMode): void {
  // Coming into *Section* puts the plane through the middle of the work as it stands now,
  // the way turning the section on always did.
  if (next === "section" && viewMode !== "section") centreSectionOn(sectionAxis);
  viewMode = next;
  ui.viewModes.mode = next;
  applySection();
  space.mode(next);
  sayWhyEmpty(scene);
}

/** What the script said, from either kind of scene: a run that fell over still printed its
 * way to the line that broke, and that is the run whose output is worth the most. */
function showStreams(said: { readonly stdout: string; readonly stderr: string }): void {
  ui.panel.stdout = said.stdout;
  ui.panel.stderr = said.stderr;
}

// ---- the sidebar: the project, and only the project -------------------------------

/** Whether the sidebar and the centre are sharing the room rather than sitting side by side -
 * the one width at which putting the sidebar away means anything. */
const sharing = (): boolean => window.matchMedia("(max-width: 1000px)").matches;

// The sidebar is the project and its files and nothing else (decision-12), so the rail has one
// button, which says the sidebar is showing - and which, on a narrow window, is how it is
// asked for and put away again, since there it takes the centre's place.
ui.railFiles.setAttribute("aria-pressed", "true");
ui.railFiles.addEventListener("click", () => {
  // Side by side there is nowhere for the sidebar to go, and a click that silently did nothing
  // would be worse than one that re-shows.
  if (sharing() && ui.shell.classList.contains("is-open")) {
    ui.shell.classList.remove("is-open");
    return;
  }
  // "The maker asked for the sidebar", which is only ever true of a click. Setting it on the
  // first paint instead is what made a narrow window open on the sidebar with the script and
  // the view nowhere to be seen.
  ui.shell.classList.add("is-open");
});

// ---- the editor group: the script, its values, and any sheet or report opened beside them ----

/** A document the editor group can show: the open script, another of the open project's
 * scripts, its values file, one of the sheets a run nested, or the report of the body dropped
 * on the view.
 *
 * Every script in the project has a tab, and only the open one is ever in front: clicking
 * another's opens *it* - into the editor, and as what Run runs (decision-9: "the script you
 * have open runs", while a fresh open of the project runs its `entry`). */
type Doc =
  | { readonly kind: "script" }
  | { readonly kind: "other"; readonly name: string }
  | { readonly kind: "values" }
  | { readonly kind: "sheet"; readonly name: string }
  | { readonly kind: "report" };

const SCRIPT: Doc = { kind: "script" };
const VALUES: Doc = { kind: "values" };
const REPORT: Doc = { kind: "report" };
const sheetDoc = (name: string): Doc => ({ kind: "sheet", name });

/** The id of a document's tab, which is also what tells two documents apart. */
const tabId = (doc: Doc): string =>
  doc.kind === "sheet" ? `tab-sheet-${doc.name}` : doc.kind === "other" ? `tab-file-${doc.name}` : `tab-${doc.kind}`;

/** The sheets open as tabs, in the order they were opened. The script and its values are not
 * in this list: they are always the first two tabs and cannot be closed, because closing the
 * two documents that *are* the project is not a thing worth being able to do. */
let openSheets: string[] = [];
/** Whether the report has a tab. There is one body and one report, so one flag; the tab is
 * shut by its close button and by the chip forgetting the body, and opened by the report
 * arriving or the chip asking for it again. */
let reportOpen = false;
/** Which document is in front. */
let front: Doc = SCRIPT;
/** The line the script is failing on, so a redrawn tab strip keeps its mark. */
let failingLine: number | null = null;

/** Drop the tabs for sheets this run no longer makes, so no tab points at nothing. */
function keepSheetTabs(sheets: readonly SheetView[]): void {
  const names = new Set(sheets.map((sheet) => sheet.name));
  openSheets = openSheets.filter((name) => names.has(name));
  if (front.kind === "sheet" && !names.has(front.name)) front = SCRIPT;
  drawTabs();
  showDocument();
}

function drawTabs(): void {
  ui.editorTabs.replaceChildren();
  for (const name of scriptsOf(opened(workspace))) {
    ui.editorTabs.append(tabFor(name === workspace.script ? SCRIPT : { kind: "other", name }, name));
  }
  ui.editorTabs.append(tabFor(VALUES, BENCH));
  for (const name of openSheets) ui.editorTabs.append(tabFor(sheetDoc(name), name));
  if (reportOpen) ui.editorTabs.append(tabFor(REPORT, body.name()));
}

/** Put the report in front, on a tab named for the file it measures. */
function openReport(): void {
  ui.reportText.textContent = body.report() ?? "";
  reportOpen = true;
  front = REPORT;
  drawTabs();
  showDocument(front);
}

/** Take the report's tab away, and the document with it if it was in front. */
function closeReport(): void {
  reportOpen = false;
  ui.reportText.textContent = "";
  if (front.kind === "report") front = SCRIPT;
  drawTabs();
  showDocument();
}

/** One tab, for `doc`, reading `label`. */
function tabFor(doc: Doc, label: string): HTMLButtonElement {
  const tab = document.createElement("button");
  tab.type = "button";
  tab.className = "tab";
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-selected", String(tabId(doc) === tabId(front)));
  tab.id = tabId(doc);
  if (doc.kind === "script" && failingLine !== null) tab.dataset["flag"] = "error";
  if (doc.kind === "values" && opened(workspace).kept.unreadable !== undefined) tab.dataset["flag"] = "error";
  const text = document.createElement("span");
  text.className = "name";
  text.textContent = label;
  tab.append(text);
  tab.addEventListener("click", () => {
    if (doc.kind === "other") openScript(doc.name);
    else showDocument(doc);
  });
  if (doc.kind === "sheet" || doc.kind === "report") {
    const shut = document.createElement("button");
    shut.type = "button";
    shut.className = "tab-close";
    shut.title = `Close ${label}`;
    shut.textContent = "✕";
    shut.addEventListener("click", (event) => {
      event.stopPropagation();
      if (doc.kind === "report") {
        closeReport();
        return;
      }
      openSheets = openSheets.filter((one) => one !== doc.name);
      if (tabId(front) === tabId(doc)) front = SCRIPT;
      drawTabs();
      showDocument();
    });
    tab.append(shut);
  }
  return tab;
}

/** Whether `doc` has a tab to come to the front on. */
const isOpen = (doc: Doc): boolean =>
  doc.kind === "sheet"
    ? openSheets.includes(doc.name)
    : doc.kind !== "other" && (doc.kind !== "report" || reportOpen);

/** Open another of the open project's scripts: into the editor, and as what Run runs. Nothing
 * about the project changes - its `entry` included - so nothing is written; which script this
 * browser has open is remembered here (`show`), not on the host. */
function openScript(name: string): void {
  const next = withScript(workspace, name);
  if (next === workspace) return;
  show(next);
  code.replace(openSource(next));
  showDocument(SCRIPT);
  window.clearTimeout(timer);
  runNow();
}

/** Bring one document to the front. Called with no argument it shows whatever is already in
 * front; asked for a sheet or a report that is not open, it shows the script. */
function showDocument(doc: Doc = front): void {
  front = isOpen(doc) ? doc : SCRIPT;
  ui.panelScript.hidden = front.kind !== "script";
  ui.panelValues.hidden = front.kind !== "values";
  ui.panelSheet.hidden = front.kind !== "sheet";
  ui.panelReport.hidden = front.kind !== "report";
  if (front.kind === "sheet") {
    const name = front.name;
    const sheet = scene?.sheets.find((one) => one.name === name);
    ui.sheetDrawing.src = sheet === undefined ? "" : pictured(sheet.svg);
    ui.sheetDrawing.alt = `the nest for ${name}`;
  }
  for (const tab of ui.editorTabs.querySelectorAll('[role="tab"]')) {
    tab.setAttribute("aria-selected", String(tab.id === tabId(front)));
  }
  // The tree marks the file in front, as the tab strip does.
  showFiles();
}

/** Mark the script's tab while it has a failing line, so a person reading a sheet can see
 * there is something to look at without the document being taken away from them. */
function flagScript(line: number | null): void {
  failingLine = line;
  const tab = document.getElementById("tab-script");
  if (tab === null) return;
  if (line === null) delete tab.dataset["flag"];
  else tab.dataset["flag"] = "error";
}

ui.inspector.addEventListener("sheet-open", (event) => {
  const { name } = event.detail;
  if (!openSheets.includes(name)) openSheets.push(name);
  front = sheetDoc(name);
  drawTabs();
  showDocument(front);
});

// ---- selection: what the inspector is about ---------------------------------------

/** The ref lit in the view, wherever it was clicked - a face, a part, a row of the tree, a place
 * of a finding. One owner, so `Mod-I` needs to know nothing about where the person clicked. */
let picked: string | null = null;

/** task-61's second pick: a shift-click on a face of a part other than `picked`'s. Cleared
 * whenever `picked` starts over - a fresh single pick is a fresh start, never half a pair
 * left over from the one before it. */
let pickedSecond: string | null = null;

/** What the inspector is about (decision-12): the project while nothing is selected, a part, a
 * face - or a reference mesh, which is not a ref at all: a body somebody else made has no ref
 * path, so `ref("…")` cannot name it, and *Insert ref* reading `picked` is right by
 * construction rather than by a check. `picked` and a reference subject are never held at
 * once - selecting either clears the other. */
let subject: Subject = PROJECT;

/** Set while a run's scene is being drawn, when the view's own "that ref is gone" is not the
 * last word on the selection (`keptAcross` is). */
let redrawing = false;

/** Whether the page is still to follow the link it was opened on - or a hash changed since - and
 * what that link asks for. The hash is not written while one is waiting, so the page's own
 * start-up, which selects nothing, does not wipe the link before a run has had a chance to
 * find what it names. */
let linking = true;
let linkAsked: Linked | null = linked(location.hash);

/** Hand the inspector the selection as it stands: the subject, what is lit, and what *Insert
 * ref* and *Insert fit* can write. */
function showSelected(): void {
  const inspector = ui.inspector;
  inspector.project = workspace.current;
  inspector.subject = subject;
  inspector.lit = picked;
  inspector.insertable = picked !== null && !hostless && writable();
  inspector.second = pickedSecond;
  inspector.fit = pickedSecond === null ? null : fitLine(picked, pickedSecond, scene?.parts ?? []);
  if (!linking) showLink();
}

/** Say the subject in the URL hash - `#part=tote`, `#face=tote/grip-left/top`, nothing for the
 * project - so a reload or a copied link opens on it. Replaced rather than pushed: a selection
 * is not a page a person goes back to, and Back should leave the app, not walk every click. */
function showLink(): void {
  const hash = linkOf(subject);
  if (hash === location.hash) return;
  history.replaceState(history.state, "", hash === "" ? `${location.pathname}${location.search}` : hash);
}

/** Select what the link asks for, in the run that has just arrived - or the project, quietly,
 * when the run has nothing by that name. */
function followLink(ok: OkScene): void {
  const found = linkedIn(linkAsked, ok.parts, ok.refs);
  linking = false;
  linkAsked = null;
  const ref = found.kind === "part" || found.kind === "face" ? found.ref : null;
  space.select(ref);
  showSelection(ref);
}

/** Put the selection `keptAcross` settled back on the page after a run: the subject, and the
 * lit ref on the view - only asked of the view when it differs, since selecting there starts a
 * shift-click pair over. */
function keepSelection(kept: Selection): void {
  subject = kept.subject;
  if (kept.lit !== picked) {
    picked = kept.lit;
    pickedSecond = null;
  }
  if (subject.kind !== "reference" && space.selected() !== picked) space.select(picked);
  showSelected();
}

// A link pasted into this tab's address bar, or Back to one: followed now when there is a scene
// to find it in, and when the next one arrives otherwise.
window.addEventListener("hashchange", () => {
  linking = true;
  linkAsked = linked(location.hash);
  if (scene !== null) followLink(scene);
});

/** Select `ref` - or nothing, which is the project: the inspector shows its subject, lit in
 * the view, its row revealed in the tree. Every way into a selection that is a ref comes
 * through here, the view's own click included. */
function showSelection(ref: string | null): void {
  picked = ref;
  pickedSecond = null;
  subject = subjectOf(ref, scene?.parts ?? []);
  space.markReference(false);
  showSelected();
}

/** Light one place of a finding without leaving the finding: the view shows it and *Insert ref*
 * writes it, and the inspector stays on the part, so the next place is one click away. */
function showPlace(ref: string): void {
  space.select(ref);
  picked = ref;
  pickedSecond = null;
  space.markReference(false);
  showSelected();
}

/** Make a reference mesh the subject - or, for `null`, go back to the project. The view marks
 * the body, and nothing else is lit: there is nothing here for *Insert ref* to write. */
function showReferenceSelection(file: string | null): void {
  picked = null;
  pickedSecond = null;
  space.select(null);
  subject = file === null ? PROJECT : { kind: "reference", file };
  space.markReference(file !== null);
  showSelected();
}

/** Say what task-61's second pick is: *Insert fit* is offered exactly when the pair can
 * honestly become a `mated(...)` line (`fitLine`), and why not when it cannot. Called from the
 * view's own `onSelectSecond` hook, the same way `showSelection` only ever reads what the view
 * already decided to highlight. */
function showSecondSelection(ref: string | null): void {
  pickedSecond = ref;
  showSelected();
}

/** Write the current pair's `mated(...)` line at the cursor - task-61's *Insert fit*. */
function insertFit(): void {
  const line = fitLine(picked, pickedSecond, scene?.parts ?? []);
  if (!("text" in line) || hostless || !writable()) return;
  showDocument(SCRIPT);
  code.insertText(line.text);
}

function insertSelected(): void {
  if (picked === null || hostless || !writable()) return;
  // The ref goes into the script, so the script is what has to be in front to see it land.
  showDocument(SCRIPT);
  code.insertRef(picked);
}

// A click in the tree is a selection exactly as a click on a face is: it lights the geometry
// up and makes it the subject, so `Mod-I` works the same from either end of the round-trip.
ui.inspector.addEventListener("ref-pick", (event) => {
  space.select(event.detail.ref);
  showSelection(event.detail.ref);
});

// The breadcrumb, a part's row and a face's part: a subject asked for by name.
ui.inspector.addEventListener("subject-pick", (event) => {
  const asked = event.detail;
  if (asked.kind === "reference") {
    showReferenceSelection(asked.file);
    return;
  }
  const ref = asked.kind === "project" ? null : asked.ref;
  space.select(ref);
  showSelection(ref);
});

// A place a finding names, lit where it is.
ui.inspector.addEventListener("place-pick", (event) => {
  showPlace(event.detail.ref);
});

ui.inspector.addEventListener("insert-ref", insertSelected);
ui.inspector.addEventListener("insert-fit", insertFit);

// A reference is chosen from the project's list. Another one than the body on the view is made
// the active one (task-49): on the view, surveyed, and named by `[reference]`; the one already
// active is simply made the subject.
ui.inspector.addEventListener("reference-pick", (event) => {
  const { file } = event.detail;
  if (file !== body.name()) {
    void chooseReference(file, true);
    return;
  }
  showReferenceSelection(file);
});

// ---- hide/show (task-67) ------------------------------------------------------

/** Which rows an eye has shut, by their own exact ref path - view state, kept here and never
 * written to the script or the host (decision-7 is about a pick; this is not one), and per
 * tab the way every other piece of viewer state already is: nothing here reaches a browser
 * store, so a second tab starts with everything shown. */
let hiddenRefs = new Set<string>();

/** Put the tree and the view back in step with `hiddenRefs`, and say on the button whether
 * there is anything left for "show all" to do. */
function applyHidden(): void {
  const list = [...hiddenRefs];
  ui.inspector.hiddenRefs = list;
  space.hide(list);
}

ui.inspector.addEventListener("ref-visibility", (event) => {
  const { ref, hidden } = event.detail;
  if (hidden) hiddenRefs.add(ref);
  else hiddenRefs.delete(ref);
  applyHidden();
});

// Isolate: every part but this one goes on the hidden set in one move - a part is a root of
// the tree the run's refs build, so the roots are exactly what "every other part" means.
ui.inspector.addEventListener("ref-isolate", (event) => {
  const roots = treeOf(scene?.refs ?? []).map((node) => node.path);
  hiddenRefs = new Set(roots.filter((root) => root !== event.detail.ref));
  applyHidden();
});

ui.inspector.addEventListener("refs-show-all", () => {
  hiddenRefs = new Set();
  applyHidden();
});

// ---- wiring ------------------------------------------------------------------

ui.run.addEventListener("click", () => {
  window.clearTimeout(timer);
  runNow();
});

ui.stop.addEventListener("click", () => {
  bridge.stop("the script was stopped.");
});

ui.fit.addEventListener("click", () => {
  space.fit();
});
ui.colourFacesToggle.addEventListener("click", () => {
  const on = ui.colourFacesToggle.getAttribute("aria-pressed") !== "true";
  ui.colourFacesToggle.setAttribute("aria-pressed", String(on));
  space.colourFaces(on);
});
ui.viewModes.addEventListener("view-mode", (event) => {
  applyMode(event.detail);
});
ui.sectionAxis.addEventListener("change", () => {
  sectionAxis = ui.sectionAxis.value as SectionAxis;
  centreSectionOn(sectionAxis);
  applySection();
});
ui.sectionPosition.addEventListener("input", () => {
  sectionPosition = Number(ui.sectionPosition.value);
  applySection();
});
ui.zoomIn.addEventListener("click", () => {
  space.zoom(ZOOM_STEP);
});
ui.zoomOut.addEventListener("click", () => {
  space.zoom(1 / ZOOM_STEP);
});

// A knob turned in the inspector is an override now and a run shortly - the same debounce as
// typing in the editor, on the same timer, so an edit to each inside it is one run carrying both.
ui.inspector.addEventListener("param-change", (event) => {
  setOverrides(withOverride(overrides, event.detail.name, event.detail.value));
  window.clearTimeout(timer);
  timer = window.setTimeout(runNow, DEBOUNCE);
});

ui.inspector.addEventListener("params-reset", () => {
  setOverrides({});
  window.clearTimeout(timer);
  runNow();
});

// A finding names the line of the script that asked for the check; that line is a way back to
// it, so the script comes forward and the cursor lands there.
document.addEventListener("goto-line", (event) => {
  showDocument(SCRIPT);
  code.goTo(event.detail.line);
});

// The inspector's export asks; the page is what touches the file system.
document.addEventListener("file-save", (event) => {
  save(event.detail.name, event.detail.data);
});
document.addEventListener("files-save-all", (event) => {
  save("bench-cut-files.zip", zip(event.detail.files));
});

/** `project` on the host before a file goes into its `prints/`: a write of it still on its way -
 * an example picked a moment ago is a project whose first files have not landed yet - is
 * waited for, the way a rename waits (`store-host.ts`), so the host does not answer that there
 * is no such project. A fresh host's untouched first example is not on the host at all, and
 * the host says so; the shipped one makes nothing a printer reads. */
async function onHost(project: string): Promise<void> {
  const box = reach;
  if (box === null) return;
  const waiting = async (): Promise<boolean> =>
    [...(await box.pending()).values()].some((one) => one.project === project);
  for (let tries = 0; (await waiting()) && tries < 25; tries += 1) {
    box.drain();
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
}

/** Hand the file called `name` - a 3MF or an STL the newest run made, as the scene carries it -
 * to the host, which writes it into the open project's `prints/` and opens it in its slicer
 * (task-86); what the host said is shown under the row it was asked from. */
async function openInSlicer(name: string, data: string): Promise<void> {
  const route = client;
  const project = workspace.current;
  if (route === null || project === "") return;
  // The run whose file this is: an answer that arrives after another run, or another project,
  // is about files no longer on screen, and is not said under a row that is not its own.
  const run = ui.inspector.files;
  const said = (one: Opening): void => {
    if (ui.inspector.files !== run) return;
    ui.inspector.opening = { ...ui.inspector.opening, [name]: one };
  };
  said({ state: "opening" });
  try {
    await onHost(project);
    const answer = await route.print(project, name, contentOf(name, data));
    if (answer.ok) {
      said({ state: "opened", message: `Opened ${answer.value.file} in ${answer.value.slicer}.` });
      log("info", "bench.slicer", "a file was opened in the slicer", {
        "bench.file": answer.value.file,
        "bench.slicer": answer.value.slicer,
      });
    } else {
      said({ state: "failed", message: answer.refusal.message });
      log("warn", "bench.slicer", "the host did not open a file in the slicer", {
        "bench.file": name,
        "bench.refused": answer.refusal.refused,
      });
    }
  } catch {
    said({ state: "failed", message: "The host did not answer, so nothing was opened." });
  }
}
document.addEventListener("slicer-open", (event) => {
  void openInSlicer(event.detail.name, event.detail.data);
});

ui.panel.addEventListener("click", () => {
  // Which way the panel was left is remembered. The component has already settled `collapsed`
  // by the time the click reaches its host.
  remember(KEYS.panel, ui.panel.collapsed ? "shut" : "open");
});

/** Open the project `next` has open: its script in the editor, its values in the panel and on
 * their tab, nothing still selected from the project before, and a run.
 *
 * Kept, because what is open may be new - a project just made, duplicated or adopted - and a
 * keep of a workspace whose projects did not change writes nothing (`project-files.ts`), so
 * switching between projects never touches the host. */
function load(next: Workspace): void {
  keep(next);
  showOverrides(opened(next).overrides);
  code.replace(openSource(next));
  space.select(null);
  showSelection(null);
  showDocument(SCRIPT);
  window.clearTimeout(timer);
  runNow();
  // A body already dropped may now be placed differently - or not at all - by whichever
  // project is open: the report is asked again so it never speaks of the placement a project
  // left behind, and a detection made under the project just left goes off.
  body.reopened();
  // And the body this project's own placement names, when it holds one and it is not the one
  // already on the view.
  void heldBody();
}

// ---- the explorer: the switcher, and the open project's own files -------------------------
//
// The explorer asks; the workspace, the host and the view are changed here.

/** Where the host keeps the projects, as it said - what a delete names before it moves
 * anything into the trash under it. `""` until the host has said. */
let projectsRoot = "";

/** The meshes in the open project's directory, by name, and which project that was read for -
 * they are bytes the store does not carry, so the tree asks the route for the listing. */
let meshes: readonly string[] = [];
let meshesOf = "";

const isMesh = (name: string): boolean => name.toLowerCase().endsWith(".stl");

/** Put the open project into the explorer: every project for the switcher, and this one's
 * files for the tree, with the one in front marked. */
function showFiles(): void {
  const one = opened(workspace);
  ui.explorer.projects = workspace.projects.map((each) => each.name);
  ui.explorer.current = workspace.current;
  ui.explorer.files = { scripts: scriptsOf(one), entry: one.entry, meshes: meshesOf === one.name ? meshes : [] };
  ui.explorer.front = front.kind === "values" ? BENCH : front.kind === "script" ? workspace.script : "";
  ui.explorer.root = projectsRoot;
  const named = one.reference?.["file"];
  ui.explorer.active = typeof named === "string" ? named : null;
  showReferenceRows();
}

/** Ask the route which meshes the open project's directory holds, and show them. A project not
 * on the host yet holds none. */
async function readMeshes(): Promise<void> {
  const project = workspace.current;
  // Asked of the root first: a project not written yet is not a directory, and asking for its
  // files would be a 404 in the console for nothing that went wrong.
  const there = await client?.projects().catch(() => null);
  const on = there?.ok === true && there.value.projects.includes(project);
  const listed = on ? await client?.files(project).catch(() => null) : null;
  if (workspace.current !== project) return; // another project opened while this was asked
  meshes = listed?.ok === true ? listed.value.map((one) => one.name).filter(isMesh) : [];
  meshesOf = project;
  showFiles();
}

/** Say at the foot of the explorer where a delete put what it moved. */
function sayMoved(what: string, trashed: string | null): void {
  const where = trashed ?? ".trash/";
  ui.explorer.said = `${what} moved to ${projectsRoot === "" ? where : `${projectsRoot}/${where}`}`;
}

ui.explorer.addEventListener("project-new", () => {
  load(created(workspace, UNTITLED, STARTER));
  code.focus();
});
ui.explorer.addEventListener("project-open", (event) => {
  load(switched(workspace, event.detail.name));
});
ui.explorer.addEventListener("project-duplicate", (event) => {
  load(duplicated(workspace, event.detail.name));
});

/** A project called something else: its directory moved as one on the host - meshes and all -
 * and then the workspace renamed, which writes only what else the rename changed (a script
 * named for the project is renamed with it). */
ui.explorer.addEventListener("project-rename", (event) => {
  const { from, to } = event.detail;
  void (async () => {
    if (store === null) return;
    const moved = await store.renameProject(from, to).catch((problem: unknown) => ({
      ok: false as const,
      message: String(problem),
    }));
    if (!moved.ok) {
      showFailure(`${from} was not renamed: ${moved.message}.`);
      return;
    }
    keep(renamed(workspace, from, to));
    if (workspace.current === to) void readMeshes();
  })();
});

/** A project put away: its whole directory into the trash on the host, then gone from the
 * workspace - opening its neighbour when it was the one open. */
ui.explorer.addEventListener("project-delete", (event) => {
  const { name } = event.detail;
  void (async () => {
    if (store === null) return;
    const moved = await store.trashProject(name).catch((problem: unknown) => ({
      ok: false as const,
      message: String(problem),
    }));
    if (!moved.ok) {
      showFailure(`${name} was not deleted: ${moved.message}.`);
      return;
    }
    const next = deleted(workspace, name, STARTER);
    if (name === workspace.current) load(next);
    else keep(next);
    sayMoved(name, moved.trashed === null ? null : `${moved.trashed}/`);
  })();
});

/** A row in the tree: the values document to its tab, a script into the editor, a mesh onto
 * the view - where its survey opens in the editor group beside the script. */
ui.explorer.addEventListener("file-open", (event) => {
  const { name } = event.detail;
  if (name === BENCH) {
    showDocument(VALUES);
    showFiles();
  } else if (name in opened(workspace).scripts) {
    if (name === workspace.script) showDocument(SCRIPT);
    else openScript(name);
    showFiles();
  } else if (isMesh(name)) {
    void chooseReference(name, false);
  }
});

ui.explorer.addEventListener("file-rename", (event) => {
  keep(scriptRenamed(workspace, event.detail.from, event.detail.to));
});

ui.explorer.addEventListener("file-duplicate", (event) => {
  const next = scriptCopied(workspace, event.detail.name);
  if (next === workspace) return;
  keep(next);
  code.replace(openSource(next));
  showDocument(SCRIPT);
  window.clearTimeout(timer);
  runNow();
});

/** A file put away: a script by the store, which moves it into the trash as it lands; a mesh
 * straight through, since the store does not carry meshes - and off the view if it was there. */
ui.explorer.addEventListener("file-delete", (event) => {
  const { name } = event.detail;
  if (isMesh(name)) {
    void deleteMesh(name);
    return;
  }
  const was = workspace.script;
  const next = scriptRemoved(workspace, name);
  if (next === workspace) return;
  keep(next);
  sayMoved(name, null);
  if (was === name) {
    code.replace(openSource(next));
    showDocument(SCRIPT);
    window.clearTimeout(timer);
    runNow();
  }
});

async function deleteMesh(name: string): Promise<void> {
  if (client === null || !writable()) return;
  const project = workspace.current;
  const said = await (async () => {
    const got = await client.read(project, name);
    if (!got.ok) return got;
    return client.remove(project, name, got.value.version.version);
  })().catch((problem: unknown) => ({ ok: false as const, refusal: { message: String(problem) } }));
  if (!said.ok) {
    showFailure(`${name} was not deleted: ${said.refusal.message}.`);
    return;
  }
  sayMoved(name, said.value.trashed);
  // The table naming it goes with it - placement and all - as the question said it would:
  // nothing is placed that is not there (decision-4).
  if (opened(workspace).reference?.["file"] === name && workspace.current === project) {
    keep(withReference(workspace, null));
  }
  if (body.name() === name) forgetBody();
  await readMeshes();
}

// A project leaves as one archive: its scripts, and its document named for its entry - the
// pair `tools/build.py` runs from a directory today (`<script>.py` beside `<script>.toml`), so
// what was kept on one host can be run, kept in a repository, or opened in another. The same
// document as `bench.toml`, `[project]` table and all; `tools.build` reads `[values]` and
// `[reference]` out of it and passes over the rest. Downloading the directory itself, with
// `bench.toml` in it, waits for `tools.build` to read one (task-50).
ui.explorer.addEventListener("project-download", (event) => {
  const one = workspace.projects.find((each) => each.name === event.detail.name);
  if (one === undefined) return;
  save(`${one.name}.zip`, zip({ ...one.scripts, [tomlName(one.entry)]: valuesDocument(one) }));
});

// And arrives the same way: each script picked becomes a project, with the values of the
// `.toml` of the same stem when that was picked too, and a values file picked on its own goes
// to the open project. The explorer only asked; reading the files is this page's to do.
ui.explorer.addEventListener("project-import", (event) => {
  void importFiles(event.detail.files);
});

/** Open what was picked - or, when any of it cannot be read, open none of it and say why.
 * One rule for the pick rather than half an import and a message the next run's scene would
 * wipe from the panel; it is also what `tools/build.py` does with a values file it cannot
 * read. */
async function importFiles(picked: readonly File[]): Promise<void> {
  const texts = await Promise.all(
    picked.map(async (file) => [file.name, await file.text()] as const),
  );
  const scripts = texts.filter(([name]) => name.endsWith(".py"));
  const documents = new Map(texts.filter(([name]) => name.endsWith(".toml")));
  const tables = new Map<string, Overrides>();
  const references = new Map<string, ReferenceTable | null>();
  const problems: string[] = [];
  for (const [name, text] of documents) {
    const found = fromToml(text);
    if (found.ok) {
      tables.set(name, found.values);
      references.set(name, found.reference);
    } else {
      problems.push(`${name}: ${found.problem}`);
    }
  }
  // A values file belongs to the script of its stem. Picked alone it is for the project that
  // is open; picked beside scripts none of which is its own, it is for a script that is not
  // here, and saying so beats quietly dropping it.
  const alone = scripts.length === 0 && documents.size === 1;
  for (const name of documents.keys()) {
    if (!alone && !scripts.some(([script]) => tomlName(script) === name)) {
      problems.push(`${name}: no ${stemOf(name)}.py was opened with it`);
    }
  }
  if (problems.length > 0) {
    showFailure(`Nothing was opened.\n\n${problems.join("\n")}`);
    return;
  }
  if (alone && !writable()) {
    showFailure(
      `Nothing was opened: a values file picked on its own goes into ${workspace.current}, which is ` +
        "open read-only here because somebody else is writing it.",
    );
    return;
  }
  if (alone) {
    const [table] = tables.values();
    const [reference] = references.values();
    const [text] = documents.values();
    // What the file holds beyond the values and the placement comes with them, so a
    // `[[measured]]` in a picked document is not dropped on the way into the project.
    keep(withKept(withReference(workspace, reference ?? null), keptOf(text ?? "")));
    setOverrides(table ?? {});
    window.clearTimeout(timer);
    runNow();
    return;
  }
  let next = workspace;
  for (const [name, source] of scripts) {
    const document = tomlName(name);
    next = created(
      next,
      stemOf(name),
      source,
      tables.get(document) ?? {},
      references.get(document) ?? null,
      keptOf(documents.get(document) ?? ""),
    );
  }
  if (next !== workspace) load(next);
}

// A picked example opens as a file of its own - never over the script being written - and runs.
ui.examples.names = Object.keys(EXAMPLES).sort();
ui.examples.addEventListener("example-pick", (event) => {
  const text = EXAMPLES[event.detail.name];
  if (text === undefined) return;
  load(withExample(workspace, event.detail.name, text));
});

// The examples above came from the bundle, not the disk; say so before anyone picks one that
// isn't what they think it is. Silent everywhere but `dev` and `preview`, where the route
// answering this exists - see `src/staleness.ts`.
void bundleStale().then((isStale) => {
  ui.staleBundle.hidden = !isStale;
  ui.staleBundle.textContent = isStale ? STALE_MESSAGE : "";
  ui.staleBundle.title = isStale ? STALE_HINT : "";
});

document.addEventListener("keydown", (event) => {
  // The editor has its own keymap for these; don't act on them twice.
  if (event.defaultPrevented) return;
  if (event.key === "Escape") {
    space.select(null);
    showSelection(null);
    return;
  }
  const mod = event.metaKey || event.ctrlKey;
  // Mod+I, not Mod+Shift+I: that one is DevTools in every browser but headless chromium.
  if (mod && !event.shiftKey && !event.altKey && event.key.toLowerCase() === "i") {
    event.preventDefault();
    insertSelected();
    return;
  }
  if (mod && event.key === "Enter") {
    event.preventDefault();
    window.clearTimeout(timer);
    runNow();
    return;
  }
  // Mod+\ alone: CodeMirror has Mod+Alt+\ (indent) and Mod+Shift+\ (the matching bracket).
  if (mod && !event.shiftKey && !event.altKey && event.key === "\\") {
    event.preventDefault();
    chooseLayout(nextLayout(layout));
  }
});

// ---- the layout: how the centre is shared -------------------------------------

/** How the centre is shared now - Code, Split or View (`layout.ts`). */
let layout: Layout = FIRST_LAYOUT;

function showLayout(next: Layout): void {
  layout = next;
  ui.groups.dataset["layout"] = next;
  ui.layout.layout = next;
}

/** A layout the person chose, by the control or the shortcut: shown, and remembered for this
 * browser - which may refuse, and then the choice lasts until the page does. */
function chooseLayout(next: Layout): void {
  showLayout(next);
  remember(KEYS.layout, next);
}

ui.layout.shortcut = "Ctrl/Cmd+\\";
ui.layout.addEventListener("layout-pick", (event) => chooseLayout(event.detail.layout));

// ---- first paint --------------------------------------------------------------

/** What is on screen before the store has answered: the shell, with the panel as it was left -
 * folded, unless it was last opened - and the centre in the layout this browser last chose.
 * Everything here is about this browser rather than about a project, so none of it waits on
 * anything. */
showDocument(SCRIPT);
ui.panel.collapsed = remembered(KEYS.panel) !== "open";
showLayout(layoutOf(remembered(KEYS.layout)));
setState("boot", "loading Python…");

/** Find the host, ask it for the projects, put the one this browser had open on screen, and
 * start it.
 *
 * The one place that waits. A page with no host says so and goes no further (AC#5). A store
 * that cannot be read is not a host with nothing kept: the first would start a person's work
 * again from scratch, so it says so and leaves the projects alone rather than writing over them
 * - `store` is let go, so no edit made afterwards is written anywhere.
 */
async function boot(): Promise<void> {
  // Decided once, before anything below reads or writes a project.
  const chosen = await chosenStore();
  if ("none" in chosen) {
    showNoHost(chosen.none);
    return;
  }
  const found = chosen.store;
  store = found;
  if (reach !== null) {
    reach.subscribe(showReach);
    showReach(reach.state());
  }
  // Asked for as soon as a project is on screen (`show`), and followed from then on.
  if (client !== null) {
    lease = leasing(client);
    lease.subscribe(standingChanged);
    // Where the projects are, for a delete to name before it moves anything into the trash.
    void client
      .projects()
      .then((listed) => {
        if (!listed.ok) return;
        projectsRoot = listed.value.root.replace(/[/\\]+$/, "");
        showFiles();
      })
      .catch(() => undefined);
  }

  let kept: string | null = null;
  try {
    kept = await found.load();
  } catch (problem: unknown) {
    store = null;
    log("error", "bench.store", "the projects could not be read", {
      "bench.store.kind": found.kind,
      "bench.store.problem": String(problem),
    });
    setState("error", "your projects could not be read", true);
    showFailure(
      `The projects kept on the ${found.kind} could not be read: ${String(problem)}.` +
        " Nothing has been changed. Reload once whatever is wrong is put right.",
    );
    return;
  }

  const read = restored(kept);
  fresh = read === null;
  show(read === null ? firstWorkspace() : reopened(read));
  if (fresh) {
    // "saved to host" would be true of no edits and false of the project on screen, which is
    // on no disk yet. The outbox's next state - the first write - says the rest.
    ui.reach.textContent = "not on host yet";
    ui.reach.title = "this example is written to the host the first time something in it is changed";
    ui.reach.dataset.state = "boot";
  }
  showOverrides(opened(workspace).overrides);
  showSelection(null);

  const source = openSource(workspace);
  code.replace(source);
  // `replace` is a change like any other, so it has started a debounce that would run the
  // script a beat after this does. The run below is the one that should happen.
  window.clearTimeout(timer);

  // Asked beside the run rather than before it: nothing waits on the answer.
  void offerAdoption();

  // A script that hung last time is not started again by itself: a reload would otherwise
  // replay the runaway and the tab would read as "booting" for ever.
  if (remembered(KEYS.hang) === hashOf(source)) {
    held = true;
    setState("error", "this script was stopped last time; press Run to try it again", true);
    showFailure(
      "This script did not finish the last time it ran, so it was stopped and has not been" +
        " run again. Press Run to try it anyway, or edit it first.",
    );
    return;
  }
  runNow();
  void heldBody();
}

void boot();
