/** The app: a workbench. A rail that says what the sidebar is, the script beside the view, a
 * panel across the bottom and a status bar under everything. Python runs in a worker.
 *
 * This module is the wiring and the run's state - what is running, what hung, the override
 * table, what is selected, which container is open and which documents are - and nothing it
 * can hand to a module of its own. The projects kept and which is open are `files.ts`, their
 * values as the TOML document they are kept and shown as is `values.ts`, what the browser
 * remembers is `storage.ts`, the wording of the status bar and the hints is `status.ts`, the
 * files a run made are `exports.ts`, the 3D pane that loads on demand is `deferred3d.ts`, and
 * every fact about a scene - counts, panes, placements - arrives from Python already worked out.
 *
 * **The view is a pane, never a tab.** Every other surface here can be covered by something
 * else; the view cannot. Selecting a ref - from the tree, from the editor's cursor, from a
 * click on a face - highlights geometry, and a highlight on a surface that is not on screen is
 * not a feature. So cut sheets open as tabs in the *editor* group, beside the script and its
 * values file, and the view keeps its own half of the centre whatever else is open. The
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
import "./components/organisms/examples-menu";
import "./components/organisms/explorer";
import "./components/organisms/panel";
import "./components/organisms/params";
import "./components/organisms/refs-tree";
import "./components/organisms/sheets";

import { type DetectOutcome, type SurveyOutcome, connect } from "./bridge";
import type { BenchExamplesMenu } from "./components/organisms/examples-menu";
import type { BenchExplorer } from "./components/organisms/explorer";
import type { BenchPanel } from "./components/organisms/panel";
import type { BenchParams } from "./components/organisms/params";
import type { BenchRefsTree } from "./components/organisms/refs-tree";
import type { BenchSheets } from "./components/organisms/sheets";
import { buttons } from "./components/styles";
import { deferred3d } from "./deferred3d";
import { save, zip } from "./downloads";
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
import {
  type NamedOrigin,
  between,
  distances,
  fieldText,
  fieldValue,
  mm,
  resolvedOrigin,
  resolvedUp,
  shown,
} from "./pick";
import type { OkScene, PartView, Scene, SheetView } from "./scene";
import { STALE_HINT, STALE_MESSAGE, bundleStale } from "./staleness";
import { HOW_TO_SELECT, failing, made, noBodiesReason, readOnlyWords, tally } from "./status";
// `remember`/`forget` are still here for what belongs to this browser rather than to a
// project - the hang fingerprint, the rail's container, the panel. The projects themselves
// go through `store` (see `store.ts` on what does not travel).
import { type Host, host as hostClient } from "./host";
import { type OutboxState, outbox } from "./outbox";
import { type Leasing, identity, leasing } from "./leasing";
import { KEYS, forget, hashOf, remember, remembered } from "./storage";
import type { ProjectStore } from "./store";
import { hostStore } from "./store-host";
import { localStore } from "./store-local";
import { type Level, attach, consoleSink, isLevel, log, timed, userTimingSink } from "./telemetry";
import {
  BENCH,
  type ReferenceTable,
  type ReferenceValue,
  fromToml,
  keptOf,
  placing,
  stemOf,
  tomlName,
} from "./values";
// A type only: `viewer3d` itself is fetched when the first scene lands (`deferred3d`), and a
// type import is erased, so naming the shape a pick comes back as costs the bundle nothing.
import type { DetectHit } from "./viewer3d";

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
  insert: need<HTMLButtonElement>("insert"),
  insertFit: need<HTMLButtonElement>("insert-fit"),
  fitWhy: need<HTMLSpanElement>("fit-why"),
  shell: need<HTMLDivElement>("shell"),
  rail: need<HTMLElement>("rail"),
  railProblems: need<HTMLButtonElement>("rail-problems"),
  railProblemCount: need<HTMLSpanElement>("rail-problem-count"),
  railParamCount: need<HTMLSpanElement>("rail-param-count"),
  explorer: need<BenchExplorer>("explorer"),
  examples: need<BenchExamplesMenu>("examples-menu"),
  refsTree: need<BenchRefsTree>("refs-tree"),
  refsCount: need<HTMLSpanElement>("refs-count"),
  referencesSaid: need<HTMLParagraphElement>("references-said"),
  sheetsList: need<BenchSheets>("sheets-list"),
  sheetCount: need<HTMLSpanElement>("sheet-count"),
  noHost: need<HTMLDivElement>("no-host"),
  noHostWhy: need<HTMLParagraphElement>("no-host-why"),
  adopt: need<HTMLDivElement>("adopt"),
  adoptList: need<HTMLUListElement>("adopt-list"),
  adoptYes: need<HTMLButtonElement>("adopt-yes"),
  adoptNo: need<HTMLButtonElement>("adopt-no"),
  lease: need<HTMLDivElement>("lease"),
  leaseTitle: need<HTMLParagraphElement>("lease-title"),
  leaseWhy: need<HTMLParagraphElement>("lease-why"),
  leaseAsk: need<HTMLParagraphElement>("lease-ask"),
  leaseTake: need<HTMLButtonElement>("lease-take"),
  leaseConfirm: need<HTMLDivElement>("lease-confirm"),
  leaseConfirmText: need<HTMLParagraphElement>("lease-confirm-text"),
  leaseTakeYes: need<HTMLButtonElement>("lease-take-yes"),
  leaseTakeNo: need<HTMLButtonElement>("lease-take-no"),
  standing: need<HTMLSpanElement>("standing"),
  paramsUnkept: need<HTMLParagraphElement>("params-unkept"),
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
  selection: need<HTMLSpanElement>("selection"),
  params: need<BenchParams>("params"),
  paramCount: need<HTMLSpanElement>("param-count"),
  reset: need<HTMLButtonElement>("reset"),
  panel: need<BenchPanel>("run-panel"),
  reference: need<HTMLSpanElement>("reference"),
  referenceName: need<HTMLSpanElement>("reference-name"),
  referenceReport: need<HTMLButtonElement>("reference-report"),
  referenceDetect: need<HTMLButtonElement>("reference-detect"),
  referenceClear: need<HTMLButtonElement>("reference-clear"),
  pick: need<HTMLElement>("pick"),
  pickFrame: need<HTMLSpanElement>("pick-frame"),
  pickRead: need<HTMLParagraphElement>("pick-read"),
  pickAsOrigin: need<HTMLButtonElement>("pick-as-origin"),
  pickAsCorner: need<HTMLButtonElement>("pick-as-corner"),
  pickAsUp: need<HTMLButtonElement>("pick-as-up"),
  pickOrigin: need<HTMLInputElement>("pick-origin"),
  pickUp: need<HTMLInputElement>("pick-up"),
  pickAlong: need<HTMLInputElement>("pick-along"),
  pickWrite: need<HTMLButtonElement>("pick-write"),
  pickUnplace: need<HTMLButtonElement>("pick-unplace"),
  pickWhy: need<HTMLParagraphElement>("pick-why"),
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
  // The panel says it too, rather than "the run is clean" about a run that never happened.
  ui.panel.error = `There is no host behind this page. ${why}`;
  ui.reach.hidden = false;
  ui.reach.textContent = "no host";
  ui.reach.title = why;
  ui.reach.dataset.state = "error";
  for (const away of [ui.rail, need<HTMLElement>("sidebar"), ui.examples, ui.editorTabs, ui.panelScript]) {
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
  // that was - so the chip is said again for whichever project is open now, and the pick
  // panel with it, since what it will let a maker do depends on that very answer.
  showReferenceChip();
  showPickState();
  showAdoption();
  // The lease follows the open project: a different one is let go of and this one asked for.
  lease?.open(next.current);
  showStanding();
}

// ---- the write lease: who may write the open project -----------------------------------

/** Say where this tab stands on the open project, everywhere it changes what a person can do:
 * the notice over the editor with whose it is, the status bar, the editor taking typing or not,
 * the knobs' own container, and every control that would write. */
function showStanding(): void {
  const standing = lease?.standing() ?? null;
  const reading = standing?.kind === "reader" && standing.project === workspace.current ? standing : null;
  const can = writable();
  code.setReadOnly(!can);
  ui.editor.dataset["readonly"] = String(!can);
  ui.explorer.readOnly = reading !== null;
  ui.paramsUnkept.hidden = reading === null;
  ui.insert.disabled = picked === null || !can;
  showFitState();
  showPickState();
  if (reading === null) {
    ui.lease.hidden = true;
    ui.leaseConfirm.hidden = true;
    ui.standing.hidden = true;
    if (reach !== null && reachPutAway) showReach(reach.state());
    return;
  }
  const words = readOnlyWords(reading.project, reading.holder, reading.lost);
  ui.lease.hidden = false;
  ui.leaseTitle.textContent = words.title;
  ui.leaseWhy.textContent = words.text;
  ui.leaseAsk.hidden = !ui.leaseConfirm.hidden;
  ui.leaseConfirmText.textContent =
    `Take ${reading.project} from ${reading.holder.label} at ${reading.holder.address}? From then on it ` +
    "can keep nothing: an edit it has not saved yet is refused, and it is told you took it over. " +
    "Do this when that one is somewhere you cannot reach.";
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
  if (now?.kind !== "reader") ui.leaseConfirm.hidden = true;
  showStanding();
}

ui.leaseTake.addEventListener("click", () => {
  ui.leaseConfirm.hidden = false;
  showStanding();
});

ui.leaseTakeNo.addEventListener("click", () => {
  ui.leaseConfirm.hidden = true;
  showStanding();
});

ui.leaseTakeYes.addEventListener("click", () => {
  ui.leaseConfirm.hidden = true;
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
    setState("ok", tally(scene.summary), failing(scene.summary));
    return;
  }
  setState("ok", "ready");
}

/** Put a failure in front of somebody: the panel holds it, and the panel comes forward. */
function showFailure(message: string): void {
  ui.panel.error = `${message}\n\n${RELOAD_HINT}`;
  ui.panel.show("problems");
}

// ---- the three pieces --------------------------------------------------------

/** The view. A click in it is the selection, so `Mod-I` inserts the ref it names, the tree
 * reveals the row, and the editor's cursor lights up what it is pointing at. */
const space = deferred3d(ui.canvas3d, {
  onSelect(ref) {
    showSelection(ref);
  },
  onSelectSecond(ref) {
    showSecondSelection(ref);
  },
  onDetectPick(hit) {
    detectedPicked(hit);
  },
});

/** A body somebody else made, dropped on the view.
 *
 * Read once, held as base64, and handed to every run after it as `reference`, so a script
 * can measure the thing it is copying - `survey(reference)` - while it writes the thing that
 * replaces it. A second drop replaces the first.
 */
let reference: string | null = null;

/** What the dropped body was called, which is what its report's tab is called. */
let referenceName = "";

/** The survey of the dropped body, written out - asked of the worker once per drop, and kept
 * for as long as the body is, so the tab it reads on can be shut and opened again without
 * measuring anything twice. `null` while there is no body, or while the worker is at it. */
let report: string | null = null;

/** What the chip's button says: the report is a click away, or is still being made. */
function showSurveyState(): void {
  ui.referenceReport.disabled = report === null;
  ui.referenceReport.textContent = report === null ? "measuring…" : "survey";
}

/** One flat `bench.worker.detected` found, in the terms it answered with - a plain view of
 * `bench.survey.Flat`, not the class itself, since this crossed the wire as JSON. */
interface DetectedFlat {
  readonly normal: readonly [number, number, number];
  readonly centre: readonly [number, number, number];
  readonly area: number;
}

/** Whether the view is currently colouring the dropped body's detected faces. */
let detecting = false;
/** The flats a detection last found, indexed the way `space.detect`'s own array is - or
 * `null` while nothing has been detected, which is also while a click on the backdrop
 * cannot mean anything. */
let detectedFlats: readonly DetectedFlat[] | null = null;

/** What the chip's detect button says and does: off, waiting on the worker, or on. */
function showDetectState(waiting = false): void {
  ui.referenceDetect.setAttribute("aria-pressed", String(detecting));
  ui.referenceDetect.disabled = waiting;
  ui.referenceDetect.textContent = waiting ? "detecting…" : "detect faces";
}

/** The three points this body's own `origin` words name, as the detection reported them, and
 * the distance within which a picked point *is* one of them - `bench.survey.ROUND`, read off
 * the wire rather than held here, so the snap and the survey can never hold two figures. Empty
 * and zero while nothing has been detected, which is also while nothing can be picked. */
let detectedOrigins: readonly NamedOrigin[] = [];
let detectedRound = 0;

/** The last two picks, newest first - two because the distance between two picked faces is how
 * a maker measures a wall, and there is nothing to measure until there are two. */
let picks: readonly DetectHit[] = [];

/** One flat as the readout says it. */
function saidFlat(flatIndex: number | null): string {
  const flat = flatIndex === null ? undefined : detectedFlats?.[flatIndex];
  if (flat === undefined || flatIndex === null) return "no detected face here";
  return (
    `flat ${flatIndex} · ${flat.area.toFixed(1)} mm²\n` +
    `normal ${shown(flat.normal, 4)} · centre ${shown(flat.centre)}`
  );
}

/** How far this pick is from the one before it - the wall-thickness line: between the two
 * points clicked, and, when both landed on a detected face, between those faces' own centres,
 * which is the number a caliper would give. */
function saidSpan(hit: DetectHit): string {
  const before = picks[1];
  if (before === undefined) return "";
  const lines = [`from the pick before: ${mm(between(hit.point, before.point))}`];
  const here = hit.flatIndex === null ? undefined : detectedFlats?.[hit.flatIndex];
  const there = before.flatIndex === null ? undefined : detectedFlats?.[before.flatIndex];
  if (here !== undefined && there !== undefined && hit.flatIndex !== before.flatIndex) {
    lines.push(`face centre to face centre: ${mm(between(here.centre, there.centre))}`);
  }
  return `\n${lines.join("\n")}`;
}

/** A detected face was clicked: everything the click resolved to, in the pick panel and in the
 * log. Numbers only - a measurement is never turned into script text here, which is task-14.3
 * and decision-7's own position, not a limitation of this panel. */
function detectedPicked(hit: DetectHit | null): void {
  if (hit === null) {
    ui.pickRead.textContent = "That click met the body nowhere. Click a coloured face.";
    return;
  }
  picks = [hit, ...picks].slice(0, 2);
  const away = distances(hit.vertex, detectedOrigins)
    .map((one) => `${one.name} ${mm(one.away)}`)
    .join(" · ");
  ui.pickRead.textContent =
    `${saidFlat(hit.flatIndex)}\n` +
    `hit ${shown(hit.point)}\n` +
    `corner ${shown(hit.vertex, 4)}\n` +
    `corner from ${away}${saidSpan(hit)}`;
  showPickState();
  log("info", "bench.pick", "a face was picked", {
    // A word rather than a number for "no face here": a sentinel index would read as a face.
    "bench.pick.flat": hit.flatIndex === null ? "none" : String(hit.flatIndex),
    "bench.pick.point": hit.point.join(", "),
    "bench.pick.corner": hit.vertex.join(", "),
  });
}

/** Fill `field` with a resolved value, and say in the panel what it resolved to and why. */
function assign(field: HTMLInputElement, value: ReferenceValue, what: string): void {
  field.value = fieldText(value);
  const how =
    typeof value === "string"
      ? `it is within ${mm(detectedRound, 4)} of the point that word names, so the word is what is written`
      : "the numbers it measured";
  say(`${what} = ${fieldText(value)}: ${how}.`);
}

/** Say something in the panel's own line - a refusal, or what a pick resolved to. */
function say(text: string, bad = false): void {
  ui.pickWhy.textContent = text;
  ui.pickWhy.classList.toggle("is-error", bad);
}

/** The pick panel, as the page's own state makes it: shown only while faces are being detected
 * (the one mode in which the backdrop answers a click at all), its assign buttons live only
 * once something has been picked, and its write refused while a placement is already applied -
 * because then the view, the survey and the detection are all in the placed frame, and a
 * number picked there is not the number `[reference]` asks for, which is the mesh's own.
 *
 * "What does this look like with nothing dropped?" - decision-7's own open question - answers
 * itself here: the chip that turns detection on is hidden until a body is dropped, so there is
 * no mode to be in and no panel to grey out. */
function showPickState(): void {
  const placed = matchedReference() !== null;
  ui.pick.hidden = !(detecting && reference !== null);
  ui.pickFrame.textContent = placed ? "reading the placed frame" : "";
  const hit = picks[0];
  const flat = hit?.flatIndex === null || hit === undefined ? undefined : detectedFlats?.[hit.flatIndex];
  ui.pickAsOrigin.disabled = hit === undefined || placed;
  ui.pickAsCorner.disabled = hit === undefined || placed;
  ui.pickAsUp.disabled = flat === undefined || placed;
  // A reader picks and reads every number, and writes none of them (task-47).
  ui.pickWrite.disabled = placed || !writable();
  ui.pickUnplace.hidden = !placed;
  ui.pickUnplace.disabled = !writable();
  for (const field of [ui.pickOrigin, ui.pickUp, ui.pickAlong]) field.disabled = placed;
  if (placed) {
    say(
      "This body is already placed by the open project's [reference], so every number here is " +
        "in the placed frame. Clear the placement to pick against the body as exported.",
    );
  }
}

/** The open project's `[reference]` table as a placement of the body on the view - or `null`
 * when there is no body, the project places nothing, the table only names which mesh is active
 * (`placing`), or it is about a file that is not the one on the view. decision-4's rule: a
 * placement for one file is never applied because a different one happens to be on the view. */
function matchedReference(): ReferenceTable | null {
  if (referenceName === "") return null;
  const table = opened(workspace).reference;
  if (table === null || table["file"] !== referenceName || !placing(table)) return null;
  return table;
}

/** `matchedReference()`, as the JSON text the worker takes - or `undefined` for nothing to
 * place with, which is what a run and a survey both take to mean "hand over the mesh exactly
 * as exported". */
const referenceTableJson = (): string | undefined => {
  const table = matchedReference();
  return table === null ? undefined : JSON.stringify(table);
};

/** `modulesOf(workspace)`, as the JSON text the worker takes - `undefined` for a project of
 * one script, which is most of them, so a run with nothing beside the open script mounts
 * nothing (task-50). */
const modulesJson = (): string | undefined => {
  const modules = modulesOf(workspace);
  return Object.keys(modules).length === 0 ? undefined : JSON.stringify(modules);
};

/** The references as the refs container lists them: every mesh the open project holds, and
 * the body on the view when it is not one of them (a drop a reader made, or one the host would
 * not take) - with the one on the view marked active, since that is the one everything that
 * measures is about (task-49). */
function showReferenceRows(): void {
  const held = meshesOf === workspace.current ? meshes : [];
  ui.refsTree.references = referenceName === "" || held.includes(referenceName) ? held : [...held, referenceName];
  ui.refsTree.activeReference = referenceName === "" ? null : referenceName;
}

/** Make `file`, one of the open project's meshes, the active reference in its `[reference]`
 * table - one table naming the active mesh, decision-4's grammar (task-49) - so a reload, and
 * `tools.build`, bring back the same one. A reader chooses on its own view and writes nothing.
 *
 * A table that *placed* another mesh is replaced by one that names this one and places nothing
 * yet: `[reference]` has room for one body, and the placement was of the other. Said, in the
 * refs container, rather than done quietly. */
function activate(file: string): void {
  const table = opened(workspace).reference;
  if (table?.["file"] === file || !writable()) return;
  const was = table?.["file"];
  const placed = table !== null && placing(table) && typeof was === "string";
  keep(withReference(workspace, { file }));
  ui.referencesSaid.hidden = !placed;
  ui.referencesSaid.textContent = placed
    ? `[reference] names ${file} now, placed nowhere yet: the placement it held was of ${was}, and went with it.`
    : "";
  log("info", "bench.reference", "a reference was made the active one", {
    "bench.reference.name": file,
    "bench.project": workspace.current,
  });
}

/** Put the open project's mesh `file` on the view and make it the active reference: read from
 * the project's directory, surveyed, run against. `quietly` keeps its report behind the chip,
 * for a row chosen in the refs container rather than a file opened from the tree. */
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

/** The chip beside the view: the file's name, `placed` once its project's `[reference]` names
 * it and a run has actually placed it - the word decision-4 asks for, since nothing is moved
 * silently - and `not kept` when the project's directory would not take it (`keepBody`). */
function showReferenceChip(): void {
  if (referenceName === "") return;
  const placed = matchedReference() === null ? "" : " · placed";
  ui.referenceName.textContent = `${referenceName}${placed}${bodyProblem === null ? "" : " · not kept"}`;
  ui.referenceName.title = bodyProblem === null ? "" : `not kept in the project: ${bodyProblem}`;
}

/** Why the body on the view is not in the open project's directory, when it is not - the
 * route's refusal, in its words. `null` for a body that landed, or is on its way. */
let bodyProblem: string | null = null;

/** `bytes` as base64, a chunk at a time: spreading a megabyte into `fromCharCode` at once
 * overflows the call stack, and a dropped body is comfortably a megabyte. */
function encoded(bytes: Uint8Array): string {
  let text = "";
  for (let at = 0; at < bytes.length; at += 0x8000) {
    text += String.fromCharCode(...bytes.subarray(at, at + 0x8000));
  }
  return btoa(text);
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

/** Whether the survey on its way is one nobody asked to read - a body put back on the view
 * because the open project's `[reference]` names it (`heldBody`) - so its report is kept for
 * the chip's button rather than brought in front of the script the person opened. */
let surveyQuietly = false;

/** Make `bytes`, called `name`, the body on the view: measured, run against, surveyed.
 *
 * `quietly` for a body the app put back by itself rather than one a person dropped: the run and
 * the survey are the same, but the report waits behind the chip instead of opening. */
function hold(name: string, bytes: Uint8Array, quietly: boolean): void {
  reference = encoded(bytes);
  referenceName = name;
  bodyProblem = null;
  report = null;
  // A new body invalidates any detection of the last one: its triangles are not this
  // one's, so the toggle goes off rather than colour the wrong mesh's flats onto this one.
  detecting = false;
  detectedFlats = null;
  detectedOrigins = [];
  detectedRound = 0;
  picks = [];
  space.detect(null);
  showPickState();
  log("info", "bench.reference", quietly ? "a reference was read back from the project" : "a body was put on the view", {
    "bench.reference.name": name,
    "bench.reference.bytes": bytes.length,
  });
  ui.reference.hidden = false;
  showReferenceChip();
  // A drop replaces what was there, so a selection on the body that has just gone would
  // name a row nothing holds. Cleared before the new rows go down, not after.
  if (pickedReference !== null) showSelection(null);
  showReferenceRows();
  showSurveyState();
  showDetectState();
  // The run first, so the view shows the body at once; the survey follows it in the worker
  // and its report opens when it lands. A drop is the maker asking what the body measures,
  // so it is not made to ask twice - and the two verbs it takes are not made to be known.
  runNow();
  surveyQuietly = quietly;
  bridge.survey(reference, referenceTableJson());
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
 * name is not written over: the drop only ever creates, and the chip says the body is not kept
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
  if (referenceName !== name) return false; // replaced on the view while this was being refused
  bodyProblem = problem;
  showReferenceChip();
  return false;
}

/** Put back on the view the body the open project's `[reference]` names, read from the
 * project's own directory - the placement and the body it places now survive a reload
 * together, which is what writing the drop into the project was for. Nothing when the table
 * names nothing, names the body already on the view, or names a file the directory does not
 * hold (decision-4's rule still stands: nothing is placed that is not there). */
async function heldBody(): Promise<void> {
  const one = opened(workspace);
  const file = one.reference?.["file"];
  if (typeof file !== "string" || file === referenceName || client === null) return;
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
    if (keeping) {
      // Kept beside the others, never over them, and made the active one (task-49): a second
      // drop adds a row rather than replacing the first.
      if ((await keepBody(project, file.name, bytes)) && workspace.current === project) activate(file.name);
      return;
    }
    // Read-only here: the body is on the view to be measured, and is not put in a project
    // somebody else is writing (task-47).
    bodyProblem = `${project} is open read-only here`;
    showReferenceChip();
  })();
});

ui.referenceClear.addEventListener("click", () => {
  forgetBody();
});

/** Forget the body on the view: the chip goes, its report goes with it, and the next run draws
 * the work on its own. The re-run is the point - without it the backdrop would stay on
 * screen until something else happened to run. */
function forgetBody(): void {
  reference = null;
  referenceName = "";
  report = null;
  detecting = false;
  detectedFlats = null;
  detectedOrigins = [];
  detectedRound = 0;
  picks = [];
  space.detect(null);
  showDetectState();
  showPickState();
  ui.reference.hidden = true;
  ui.referenceName.textContent = "";
  showReferenceRows();
  // The row it was selected on has gone, so the selection goes with it rather than pointing
  // at a body nothing is holding any more.
  if (pickedReference !== null) showSelection(null);
  closeReport();
  runNow();
}

/** The report, asked for again from the chip after its tab was shut. */
ui.referenceReport.addEventListener("click", () => {
  if (report !== null) openReport();
});

/** The detect toggle: off turns the backdrop back into a plain ghost at once, since nothing
 * has to be asked for to stop colouring it; on asks the worker for the same body's flats,
 * the same way a drop asks for its survey. Detection is also the pick's own mode (decision-7
 * asked for one, and this is it): the panel comes and goes with it, because the backdrop
 * answers a click only while this is on. */
ui.referenceDetect.addEventListener("click", () => {
  if (reference === null) return;
  if (detecting) {
    detecting = false;
    space.detect(null);
    showDetectState();
    showPickState();
    return;
  }
  detecting = true;
  showDetectState(true);
  showPickState();
  bridge.detect(reference, referenceTableJson());
});

/** The point the ray met, as `origin` - the general case, and what decision-7 describes: an
 * arbitrary point on a real face, written as the triple it measured. */
ui.pickAsOrigin.addEventListener("click", () => {
  const hit = picks[0];
  if (hit === undefined) return;
  assign(ui.pickOrigin, resolvedOrigin(hit.point, detectedOrigins, detectedRound), "origin");
});

/** The nearest corner of the face that was clicked, as `origin`. This is the choice that makes
 * the named word reachable at all: on a body that is an axis-aligned box - decision-4's
 * systainer foot - `Extent.low` *is* one of the mesh's own vertices, so picking the corner
 * lands on it to the last float the exporter wrote and the word is written for the right
 * reason. The point the ray met never would: no mouse lands within a hundredth of a
 * millimetre of anything. */
ui.pickAsCorner.addEventListener("click", () => {
  const hit = picks[0];
  if (hit === undefined) return;
  assign(ui.pickOrigin, resolvedOrigin(hit.vertex, detectedOrigins, detectedRound), "origin");
});

/** The picked face's own normal, as `up` - always as the triple it measured, never snapped to
 * a signed axis word: that would need a tolerance on an angle, and decision-7 says plainly
 * that bench has none to borrow. A maker who wants `+Z` types it in the field. */
ui.pickAsUp.addEventListener("click", () => {
  const hit = picks[0];
  const flat = hit?.flatIndex === null || hit === undefined ? undefined : detectedFlats?.[hit.flatIndex];
  if (flat === undefined) return;
  assign(ui.pickUp, resolvedUp(flat.normal), "up");
});

/** Commit: the three fields become the open project's `[reference]` table, in one act.
 *
 * Why one act rather than a write per pick, which is what task-18.2's rule for `[values]`
 * would suggest: a `[reference]` table is applied the moment its `file` names the dropped body
 * (`matchedReference`), and from there every run, survey and detection puts the mesh through
 * `bench.placement.placement`, which *raises* on a table missing any of `origin`, `up` or
 * `along`. A per-field write would break the run with "reference table has no 'up'" between
 * the first pick and the last, and would move the body the second pick is measured against.
 * `[values]` has no such feedback: a knob's value does not move the thing being pointed at.
 * decision-7 left this open; this is the answer, and it is the code's, not a preference.
 */
ui.pickWrite.addEventListener("click", () => {
  if (referenceName === "" || !writable()) return;
  const origin = fieldValue(ui.pickOrigin.value);
  const up = fieldValue(ui.pickUp.value);
  const along = fieldValue(ui.pickAlong.value);
  const missing = [
    origin === null ? "origin" : null,
    up === null ? "up" : null,
    along === null ? "along (typed - decision-7 designs no edge-pick)" : null,
  ].filter((one) => one !== null);
  if (origin === null || up === null || along === null) {
    say(
      `A placement is all three or none, because the run refuses a partial table: ${missing.join(", ")} still to say.`,
      true,
    );
    return;
  }
  const table: ReferenceTable = { file: referenceName, origin, up, along };
  keep(withReference(workspace, table));
  log("info", "bench.pick", "a placement was written", {
    "bench.reference.name": referenceName,
    "bench.pick.origin": fieldText(origin),
    "bench.pick.up": fieldText(up),
    "bench.pick.along": fieldText(along),
  });
  // The body now moves, so nothing measured in the old frame is worth keeping on screen: the
  // colours are asked for again under the placement, the survey with them, and the run redraws
  // the body where the table says it stands - which is what makes the chip's "placed" honest.
  replaced("the placement was written");
  say("Written. The body is placed by it now - the view, the survey and the chip all say so.");
});

/** Forget the placement, so a pick reads the body as exported again - the way back out of the
 * placed frame, and the only way to re-pick a placement this panel wrote. */
ui.pickUnplace.addEventListener("click", () => {
  if (!writable()) return;
  keep(withReference(workspace, null));
  replaced("the placement was cleared");
  say("Cleared. The body stands as exported, and a pick reads its own numbers again.");
});

/** A placement arrived or left: the body's frame changed under everything already measured
 * about it, so every measurement is dropped and asked for again under the new frame - the
 * faces, if they were being shown, the survey, and the run that draws the body.
 *
 * Nothing measured in the old frame is kept and relabelled: that is the same rule
 * `bench.worker.detected` follows for a survey, one layer up. */
function replaced(why: string): void {
  const again = detecting && reference !== null;
  detectedFlats = null;
  detectedOrigins = [];
  detectedRound = 0;
  picks = [];
  space.detect(null);
  ui.pickRead.textContent = "Click a coloured face: what it measures reads here.";
  report = null;
  showSurveyState();
  showDetectState(again);
  showPickState();
  log("info", "bench.reference", why);
  runNow();
  if (reference !== null) bridge.survey(reference, referenceTableJson());
  if (again && reference !== null) bridge.detect(reference, referenceTableJson());
}

/** The survey came back: the report opens beside the script - or, when there is none, the
 * chip says so and the run's own failure, which put the same file through the same reader,
 * has already said why in the panel. */
function surveyed(outcome: SurveyOutcome): void {
  if (reference === null) return; // cleared while the worker was at it
  if ("problem" in outcome) {
    log("warn", "bench.reference", "the dropped body was not surveyed", {
      "error.message": outcome.problem,
    });
    ui.referenceReport.disabled = true;
    ui.referenceReport.textContent = "no survey";
    return;
  }
  report = outcome.report;
  showSurveyState();
  if (surveyQuietly) surveyQuietly = false;
  else openReport();
}

/** The detection came back: the backdrop is coloured by it - or, when there is none, the
 * toggle goes back off and says why in the log, the same shape `surveyed`'s failure takes. */
function detected(outcome: DetectOutcome): void {
  if (reference === null || !detecting) return; // cleared, or turned off while the worker was at it
  if ("problem" in outcome) {
    log("warn", "bench.reference", "the dropped body's faces were not detected", {
      "error.message": outcome.problem,
    });
    detecting = false;
    showDetectState();
    return;
  }
  const found = JSON.parse(outcome.result) as {
    flat_index: readonly (number | null)[];
    flats: readonly DetectedFlat[];
    origins: readonly NamedOrigin[];
    round: number;
  };
  detectedFlats = found.flats;
  detectedOrigins = found.origins;
  detectedRound = found.round;
  space.detect(found.flat_index);
  showDetectState();
  showPickState();
}

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
  ui.params.overrides = next;
  ui.reset.disabled = Object.keys(next).length === 0;
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
      surveyed(outcome);
    },
    onDetect(outcome) {
      detected(outcome);
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
  bridge.request(code.text(), overrides, reference ?? undefined, referenceTableJson(), modulesJson());
}

function received(next: Scene): void {
  booting = false;
  ui.timing.textContent = `${((performance.now() - asked) / 1000).toFixed(1)} s`;
  if (!next.ok) {
    code.showError(next.error.line);
    flagScript(next.error.line);
    setState("error", next.error.message, true);
    ui.panel.error =
      next.error.traceback.trim() === ""
        ? next.error.message
        : `${next.error.message}\n\n${next.error.traceback.trim()}`;
    showStreams(next);
    ui.panel.show("problems");
    return;
  }
  scene = next;
  showFitState();
  // A run that got all the way here is not the thing that hung.
  forget(KEYS.hang);
  held = false;
  // The table is pruned to what the script declares, and - when it is still the table this
  // run was asked with - each value is replaced by what the run built from it, so the file
  // says what was made. Either way the same table comes back when nothing changed.
  const declared = declaredOnly(overrides, next.params);
  const built = overrides === sentWith ? asBuilt(declared, next.values) : declared;
  if (built !== overrides) setOverrides(built);
  else showValues(); // the file follows the script's order, which this run has just said
  // A run can succeed and still be wrong: a check that found an ERROR marks its line in the
  // editor exactly as a raised exception would, because a part that will not work is not a
  // detail in a list.
  code.showError(next.summary.error_line);
  flagScript(next.summary.error_line);
  code.knowRefs(next.refs);
  ui.panel.error = "";

  timed("bench.view.geometry", () => showGeometry(next), { "bench.parts": next.summary.parts });
  ui.params.params = next.params;
  countOn(ui.paramCount, ui.railParamCount, next.params.length);
  ui.refsTree.refs = next.refs;
  ui.refsTree.flagged = next.violations.flatMap((one) => [...one.refs]);
  ui.refsCount.textContent = next.refs.length === 0 ? "" : String(next.refs.length);
  ui.sheetsList.sheets = next.sheets;
  ui.sheetCount.textContent = next.sheets.length === 0 ? "" : String(next.sheets.length);
  ui.panel.violations = next.violations;
  ui.panel.warnings = next.warnings;
  ui.panel.sheets = next.sheets;
  ui.panel.files = next.files;
  showStreams(next);
  showProblemCount();
  keepSheetTabs(next.sheets);
  ui.madeChip.textContent = made(next.summary);
  // The status bar is the one place the count is said in words.
  setState("ok", tally(next.summary), failing(next.summary));
}

/** A count in two places at once - the container's own header, and the rail's badge for when
 * the container is not the one showing. */
function countOn(header: HTMLElement, badge: HTMLElement, count: number): void {
  header.textContent = count === 0 ? "" : String(count);
  badge.textContent = String(count);
  badge.hidden = count === 0;
}

function showProblemCount(): void {
  const count = ui.panel.problems;
  ui.railProblemCount.textContent = String(count);
  ui.railProblemCount.hidden = count === 0;
}

/** Draw the scene: every part with a body, standing where the stage put it, and why the view
 * is empty when none has one. */
function showGeometry(ok: OkScene): void {
  space.show(ok.parts, ok.stage, ok.sheets, ok.reference);
  space.say(noBodiesReason(ok.summary));
}

/** What the script said, from either kind of scene: a run that fell over still printed its
 * way to the line that broke, and that is the run whose output is worth the most. */
function showStreams(said: { readonly stdout: string; readonly stderr: string }): void {
  ui.panel.stdout = said.stdout;
  ui.panel.stderr = said.stderr;
  showProblemCount();
}

// ---- the sidebar: which container the rail has open -------------------------

type Container = "files" | "refs" | "parameters" | "sheets";

const CONTAINERS: readonly Container[] = ["files", "refs", "parameters", "sheets"];

const isContainer = (said: string | null): said is Container =>
  said !== null && CONTAINERS.includes(said as Container);

/** Which container is showing. Never `null`: the rail's icons switch what the sidebar *is*
 * rather than toggling it, which is VS Code's model and the one the shape was drawn for. On a
 * narrow window the sidebar takes the centre's place instead, and there it can be shut. */
let container: Container = isContainer(remembered(KEYS.container))
  ? (remembered(KEYS.container) as Container)
  : "refs";

function showContainer(next: Container, remembering = true): void {
  container = next;
  for (const name of CONTAINERS) {
    need<HTMLElement>(`container-${name}`).hidden = name !== next;
    need<HTMLButtonElement>(`rail-${name}`).setAttribute(
      "aria-pressed",
      String(name === next),
    );
  }
  if (remembering) remember(KEYS.container, next);
}

/** Whether the sidebar and the centre are sharing the room rather than sitting side by side -
 * the one width at which putting the sidebar away means anything. */
const sharing = (): boolean => window.matchMedia("(max-width: 1000px)").matches;

for (const name of CONTAINERS) {
  need<HTMLButtonElement>(`rail-${name}`).addEventListener("click", () => {
    // Clicking the container that is already showing puts the sidebar away - but only on a
    // narrow window, where it is in the centre's place. Side by side there is nowhere for it
    // to go, and a click that silently did nothing would be worse than one that re-shows.
    if (name === container && sharing() && ui.shell.classList.contains("is-open")) {
      ui.shell.classList.remove("is-open");
      return;
    }
    // "The maker asked for the sidebar", which is only ever true of a click. Setting it on
    // the first paint instead is what made a narrow window open on the sidebar with the
    // script and the view nowhere to be seen.
    ui.shell.classList.add("is-open");
    showContainer(name);
  });
}

ui.railProblems.addEventListener("click", () => {
  ui.panel.show("problems");
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
  if (reportOpen) ui.editorTabs.append(tabFor(REPORT, referenceName));
}

/** Put the report in front, on a tab named for the file it measures. */
function openReport(): void {
  ui.reportText.textContent = report ?? "";
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

ui.sheetsList.addEventListener("sheet-open", (event) => {
  const { name } = event.detail;
  if (!openSheets.includes(name)) openSheets.push(name);
  front = sheetDoc(name);
  drawTabs();
  showDocument(front);
});

// ---- selection ---------------------------------------------------------------

/** What is selected, wherever it was clicked. One owner, so `Mod-I` needs to know nothing
 * about whether the person was looking at the drawing or the tree. */
let picked: string | null = null;

/** Which dropped body is selected, when a dropped body is what is selected.
 *
 * A second field rather than a wider `picked`, because the two are not the same kind of thing
 * and only one of them is a ref: a body somebody else made has no ref path, so `ref("…")`
 * cannot name it and `resolve()` would not find it. Keeping them apart is what makes
 * *Insert ref* read `picked` and be right by construction rather than by a check. The page
 * holds both, and holds them mutually exclusive - selecting either clears the other.
 */
let pickedReference: string | null = null;

/** task-61's second pick: a shift-click on a face of a part other than `picked`'s. Cleared
 * whenever `picked` starts over - a fresh single pick is a fresh start, never half a pair
 * left over from the one before it. */
let pickedSecond: string | null = null;

/** Say what is selected, everywhere it is said: the bar, the button that acts on it, and the
 * tree, which opens whatever was shut above the row and scrolls it into view. */
function showSelection(ref: string | null): void {
  picked = ref;
  pickedSecond = null;
  // A ref is selected, or nothing is: either way no dropped body is, which is what every
  // caller of this already meant - `showSelection(null)` is how the app says "nothing".
  pickedReference = null;
  ui.selection.textContent = ref ?? HOW_TO_SELECT;
  ui.selection.classList.toggle("is-set", ref !== null);
  ui.insert.disabled = ref === null || !writable();
  ui.refsTree.selected = ref;
  ui.refsTree.selectedReference = null;
  space.markReference(false);
  showFitState();
}

/** Say that a dropped body is what is selected. The bar names the file rather than anything
 * shaped like a ref, and *Insert ref* stays off: there is nothing here for it to write. */
function showReferenceSelection(file: string | null): void {
  pickedReference = file;
  if (file !== null) {
    picked = null;
    pickedSecond = null;
    ui.refsTree.selected = null;
    space.select(null);
  }
  ui.selection.textContent = file === null ? HOW_TO_SELECT : `reference: ${file}`;
  ui.selection.classList.toggle("is-set", file !== null);
  ui.insert.disabled = true;
  ui.refsTree.selectedReference = file;
  space.markReference(file !== null);
  showFitState();
}

/** Say what task-61's second pick is: the bar grows a second line naming it, and *Insert
 * fit* is offered exactly when the pair can honestly become a `mated(...)` line - see
 * `fitLine`. Called from the view's own `onSelectSecond` hook, the same way `showSelection`
 * only ever reads what the view already decided to highlight. */
function showSecondSelection(ref: string | null): void {
  pickedSecond = ref;
  showFitState();
}

/** The part a ref belongs to, or `null` when no scene is up or nothing answers to it. */
function partOfRef(ref: string): PartView | null {
  if (scene === null) return null;
  return scene.parts.find((part) => part.ref === ref || ref.startsWith(`${part.ref}/`)) ?? null;
}

/** A part's ref as a Python identifier, the way a maker would type it by hand: `-` turned to
 * `_`, a leading digit given a `_` to sit behind. It stands in for the script's own `Part`
 * variable, which the app has no way to know (decision-7: a pick writes numbers, never a
 * script's own names) - so it is the most useful honest guess, right when a part's variable
 * is named after its label and wrong otherwise, and *Insert fit*'s line still needs reading
 * before it is trusted, the same as any inserted `ref("…")` needing the right hole to sit in. */
function fitIdentifier(ref: string): string {
  const cleaned = ref.replaceAll(/[^A-Za-z0-9_]/g, "_");
  return /^[0-9]/.test(cleaned) ? `_${cleaned}` : cleaned;
}

/** The `mated(...)` line the current pair would write, or why it cannot - a part with no
 * body (sheet, not print), or a face `plane_of` cannot frame (round, no `around=`), each say
 * so rather than *Insert fit* writing a call that only fails once the script runs. */
function fitLine(): { readonly text: string } | { readonly why: string } {
  if (picked === null || pickedSecond === null) return { why: "" };
  const fixed = partOfRef(picked);
  const moving = partOfRef(pickedSecond);
  if (fixed === null || moving === null) return { why: "" };
  if (fixed.process !== "print" || moving.process !== "print") {
    return { why: "mated puts one printed part's face on another's; a sheet part has none" };
  }
  if (fixed.frames[picked] === undefined) {
    return { why: `${picked} has no single plane - plane_of needs around= for a round face` };
  }
  if (moving.frames[pickedSecond] === undefined) {
    return { why: `${pickedSecond} has no single plane - plane_of needs around= for a round face` };
  }
  const text = `mated(${fitIdentifier(fixed.ref)}, ref(${JSON.stringify(picked)}), ${fitIdentifier(moving.ref)}, ref(${JSON.stringify(pickedSecond)}))`;
  return { text };
}

/** What the bar and *Insert fit* say about the current pair, or the lack of one.
 *
 * The button vanishes when it is disabled - `.picked button:disabled { display: none }`,
 * the same rule *Insert ref* already lives under - so there is nothing to offer with one
 * pick or none. The reason a pair cannot be written stays visible beside it regardless,
 * in `#fit-why`, which is a plain span and not under that rule: a maker shift-clicking a
 * round face should read why, not watch the button silently fail to appear. */
function showFitState(): void {
  if (pickedSecond === null) {
    ui.fitWhy.textContent = "";
    ui.insertFit.disabled = true;
    ui.insertFit.title = "";
    return;
  }
  const line = fitLine();
  ui.fitWhy.textContent = "why" in line ? line.why : "";
  ui.insertFit.disabled = !("text" in line) || hostless || !writable();
  ui.insertFit.title = "text" in line ? line.text : (line.why || "shift-click a face on another part");
}

/** Write the current pair's `mated(...)` line at the cursor - task-61's *Insert fit*. */
function insertFit(): void {
  const line = fitLine();
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
// up and fills the bar, so `Mod-I` works the same from either end of the round-trip.
ui.refsTree.addEventListener("ref-pick", (event) => {
  space.select(event.detail.ref);
  showSelection(event.detail.ref);
});

// A dropped body is selected the same way, and lights up the same way - it just has no ref to
// insert, so the bar names the file and the button stays off.
// Choosing another reference's row makes it the active one (task-49): on the view, surveyed,
// and named by `[reference]`. The row of the one already active selects it, as before.
ui.refsTree.addEventListener("reference-pick", (event) => {
  const { file } = event.detail;
  if (file !== referenceName) {
    void chooseReference(file, true);
    return;
  }
  showReferenceSelection(pickedReference === file ? null : file);
});

// ---- wiring ------------------------------------------------------------------

ui.run.addEventListener("click", () => {
  window.clearTimeout(timer);
  runNow();
});

ui.stop.addEventListener("click", () => {
  bridge.stop("the script was stopped.");
});

ui.insert.addEventListener("click", insertSelected);
ui.insertFit.addEventListener("click", insertFit);
ui.fit.addEventListener("click", () => {
  space.fit();
});
ui.zoomIn.addEventListener("click", () => {
  space.zoom(ZOOM_STEP);
});
ui.zoomOut.addEventListener("click", () => {
  space.zoom(1 / ZOOM_STEP);
});

// An edit in the panel is an override now and a run shortly - the same debounce as typing
// in the editor, on the same timer, so an edit to each inside it is one run carrying both.
ui.params.addEventListener("param-change", (event) => {
  setOverrides(withOverride(overrides, event.detail.name, event.detail.value));
  window.clearTimeout(timer);
  timer = window.setTimeout(runNow, DEBOUNCE);
});

ui.reset.addEventListener("click", () => {
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

// The panel asks; the page is what touches the file system.
document.addEventListener("file-save", (event) => {
  save(event.detail.name, event.detail.data);
});
document.addEventListener("files-save-all", (event) => {
  save("bench-cut-files.zip", zip(event.detail.files));
});

ui.panel.addEventListener("click", () => {
  // Collapsing or opening the panel changes what the rail's badge is standing in for - and
  // which way it was left is remembered, the way the rail's own container is. The component
  // has already settled `collapsed` by the time the click reaches its host.
  showProblemCount();
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
  // left behind. `keep()`, above, has already said what the chip says about it.
  if (reference !== null) {
    report = null;
    showSurveyState();
    bridge.survey(reference, referenceTableJson());
    // A detected flat's own numbers are placed coordinates too, and a different project can
    // place the same drop differently - so a detection made under the project just left is
    // turned off rather than left showing faces at the wrong numbers.
    if (detecting) {
      detecting = false;
      detectedFlats = null;
      space.detect(null);
      showDetectState();
    }
  }
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
  if (referenceName === name) forgetBody();
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
  }
});

// ---- first paint --------------------------------------------------------------

/** What is on screen before the store has answered: the shell, in the state the rail and the
 * panel were left in. Everything here is about this browser rather than about a project, so
 * none of it waits on anything. */
showContainer(container, false);
showDocument(SCRIPT);
ui.panel.collapsed = remembered(KEYS.panel) === "shut";
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
