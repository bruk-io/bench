/** The view, fetched while the first scene is on its way.
 *
 * three.js and its renderer are half a megabyte, and a static import would put that in front
 * of the editor's first paint, while Python is still booting and there is nothing to draw
 * anyway. So the view is a stand-in until the first scene arrives - it remembers what it was
 * told and hands it over once the real one has loaded.
 */
import type { MeshView, PartView, SheetView, StageView } from "./scene";
import type { SectionState, Viewer3D, Viewer3DHooks } from "./viewer3d";

export function deferred3d(container: HTMLElement, hooks: Viewer3DHooks): Viewer3D {
  let real: Viewer3D | null = null;
  let asked = false;
  let parts: readonly PartView[] = [];
  let stage: StageView | null = null;
  let sheets: readonly SheetView[] = [];
  let reference: MeshView | null = null;
  let note = "";
  let chosen: string | null = null;
  let chosenSecond: string | null = null;
  let pointed: string | null = null;
  let detected: readonly (number | null)[] | null = null;
  let section: SectionState | null = null;
  let colouring = false;
  let marked = false;
  let hidden: readonly string[] = [];

  function wake(): void {
    if (asked) return;
    asked = true;
    // `is-waiting` so this stand-in cannot be mistaken for the view's own note - they read
    // the same to a person and must not to anything looking for one of them.
    const waiting = document.createElement("div");
    waiting.className = "canvas-note is-waiting";
    waiting.textContent = "loading the view…";
    container.append(waiting);
    void import("./viewer3d").then(
      (module) => {
        waiting.remove();
        const made = module.mount(container, hooks);
        if (stage !== null) made.show(parts, stage, sheets, reference);
        made.say(note);
        // `select` clears the real view's own second pick, so it goes first and `selectSecond`
        // after - the same order a fresh shift-click pair would arrive in.
        made.select(chosen);
        made.selectSecond(chosenSecond);
        made.point(pointed);
        made.detect(detected);
        made.section(section);
        made.colourFaces(colouring);
        made.markReference(marked);
        made.hide(hidden);
        real = made;
      },
      (problem: unknown) => {
        waiting.textContent = `the view did not load: ${String(problem)}`;
      },
    );
  }

  return {
    show(given, at, cut, backdrop = null) {
      parts = given;
      stage = at;
      sheets = cut;
      reference = backdrop;
      wake();
      real?.show(given, at, cut, backdrop);
    },
    say(text) {
      note = text;
      if (text !== "") wake();
      real?.say(text);
    },
    fit: () => real?.fit(),
    zoom: (factor) => real?.zoom(factor),
    select(ref) {
      chosen = ref;
      chosenSecond = null;
      real?.select(ref);
    },
    selectSecond(ref) {
      chosenSecond = ref;
      real?.selectSecond(ref);
    },
    point(ref) {
      pointed = ref;
      real?.point(ref);
    },
    selected: () => real?.selected() ?? null,
    selectedSecond: () => real?.selectedSecond() ?? null,
    empty: () => real?.empty() ?? true,
    detect(flatIndex) {
      detected = flatIndex;
      real?.detect(flatIndex);
    },
    section(state) {
      section = state;
      real?.section(state);
    },
    colourFaces(on) {
      colouring = on;
      real?.colourFaces(on);
    },
    markReference(lit) {
      marked = lit;
      real?.markReference(lit);
    },
    hide(refs) {
      hidden = refs;
      real?.hide(refs);
    },
  };
}
