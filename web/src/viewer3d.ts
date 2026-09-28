/** The view: every part of the scene with a body - a laser part's plate, a printed part's
 * solid - and what is engraved on the plates. A click on a face, an engraved line or a line of
 * lettering gives its ref, so `Mod-I` inserts `ref("collar/set-screw")` or
 * `ref("drawer-front-1/pull")` the same way.
 *
 * **It draws what it is given.** Where each body stands, the box they fill and the floor under
 * them are worked out in Python (`bench.stage`); a mesh arrives as its triangles' corners
 * already placed, one triangle at a time, with a number per triangle naming its face; an
 * engraving arrives as segment ends and a line of lettering as the four corners of its box. So
 * this module makes no geometry of its own: it hands those buffers to three.js, colours them by
 * what is selected, and frames the camera on the box it was told about.
 *
 * **Picking.** Manifold has a `rayCast` and it is not usable for this: measured against a
 * composite it named the wrong face on every one of six hundred triangles. So three.js does
 * the raycasting, and the hit comes back as a *triangle index* - which is exactly what a
 * mesh's `ref_index` is keyed by, as a segment's index is for an engraving. That is why the
 * positions are one triangle at a time: a triangle's number is its `faceIndex`, a highlighted
 * face is three vertex colours per triangle that cannot bleed into its neighbours, and the
 * facets shade flat.
 *
 * **Coordinates.** Bench is millimetres with Z up; three.js assumes Y up, so the camera is
 * told its own up vector and the orbit follows. Nothing here rotates the geometry of its own
 * accord.
 *
 * **Three ways of looking** (decision-12). *Assembled* draws the parts where the script puts
 * them, the reference and the context bodies beside them, and no floor - an assembly has no
 * bed. *On bed* draws each printed part the way it prints on the printer's bed: the move that
 * lays it there is a matrix Python composed (`PrintingView.placement` - the same move its STL
 * is written with, then a step across the bed), applied to the body already drawn, and the
 * bed's floor and build volume are lines Python placed; the faces the run's overhang findings
 * name are painted, and a part that does not fit is tinted. Nothing else is on the bed - a cut
 * part, the reference and a context body are not printed. *Section* is *Assembled* clipped at
 * one plane - parts, reference and context bodies alike - with each kind's cut face filled in
 * where the plane passes through it (a stencil count of the surfaces behind the plane, the
 * usual capping trick: drawing only, no cross-section is computed), so a foot in its pocket
 * reads as two solids and a gap.
 *
 * **For a test to read.** A canvas is one opaque element, so what is on it is also said on
 * the container: `data-bodies` and `data-triangles` for what was drawn, `data-bounds` for the
 * box it fills, `data-selected` and `data-pointed` for the refs lit, `data-lit` for how many
 * triangles are painted as selected, `data-distance` for how far the camera stands from what
 * it looks at, `data-datum` for how long the origin's own X/Y/Z arms are drawn,
 * `data-eye` for the way from what it looks at out to the camera, as a unit direction, and
 * `data-framed` for the place a finding named that it last turned to (empty once *Fit* frames
 * everything again),
 * `data-mode` for the way of looking, `data-floor` for whether a bed's floor is drawn (only
 * ever *On bed*), `data-section` for the axis and position a section is
 * clipping at (empty unless in *Section*), `data-bed` for the printer *On bed* lays parts on
 * and `data-plates` for how many of its plates they take, `data-laid` for how many parts it
 * lays,
 * `data-unfit` for how many parts laid on it do not fit and `data-overhang` for how many
 * triangles are painted as an overhang,
 * `data-colour-faces` for whether every named face is painted its own colour (empty when off),
 * `data-hidden` for how many triangles the refs container's eye toggles are hiding right now,
 * and `data-context` and `data-context-triangles` for the bodies shown for context.
 *
 * **Context.** A body a script shows with `context(...)` is drawn translucent in a colour no
 * part wears, where Python put it. Its named faces answer a click and a hover like a part's -
 * `pipe/side-0` - but a part anywhere under the pointer wins, so a ghost round the work never
 * swallows a click meant for what is inside it, and a triangle of no name answers nothing.
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import type {
  BedView,
  ContextView,
  FrameView,
  LetteringView,
  MarksView,
  MeshView,
  PartView,
  SheetView,
  SightView,
  StageView,
} from "./scene";

const FOV = 35;
const NEAR = 0.05;
const FAR = 20_000;
const CLICK_SLOP = 4; // px of pointer travel that is still a click, not a drag
const LINE_PICK = 0.8; // mm either side of an engraved line that still picks it
const LETTER_PX = 64; // the height lettering is rendered at before it is laid on its box
const PLACE_LEAST = 0.12; // the least of the scene's diagonal a framed place is shown across

/** The way the view stands to look at the work: over the front right corner, from above - the
 * three-quarter view a maker holds a part at. `bench.views.STANDING` is the same, and a place's
 * own eye leans toward it. */
const STANDING = new THREE.Vector3(0.78, -1, 0.6).normalize();

/** Which axis a section clips along, and where along it. `position` is an absolute
 * millimetre in the scene's own coordinates - the stage's, not a fraction of the box - so a
 * section stands still while a pose knob moves the geometry through it. */
export type SectionAxis = "x" | "y" | "z";
export interface SectionState {
  readonly axis: SectionAxis;
  readonly position: number;
}

/** The three ways of looking at a scene (decision-12): where the script puts the parts, how
 * they print on the printer's bed, and the assembled scene cut at a plane. */
export type ViewMode = "assembled" | "bed" | "section";

/** The four states a face can be in, and the ink an engraving is drawn in when it is in none
 * of them. */
const BASE = new THREE.Color(0x9fb0c0);
const INK = new THREE.Color(0x2f353b);
const HOVER = new THREE.Color(0xc8d6e2);
const SELECTED = new THREE.Color(0x00aaaa);
const CURSOR = new THREE.Color(0xe38b00);

/** What a cut face is painted, unlit - a section is not lighting, and reading it as one more
 * shaded surface among the part's own would hide the one thing it is there to say: this is
 * open material, not a face the part actually has. A reference's cut and a context body's are
 * painted in their own colours, darker than their ghosts, so a foot in its pocket reads as two
 * different solids with a gap between them. */
const CUT = new THREE.Color(0xb23a2e);
const REFERENCE_CUT = new THREE.Color(0x27303a);
const CONTEXT_CUT = new THREE.Color(0xa9803d);

/** *On bed*: a face the run's overhang findings name, and a part that does not fit the bed. A
 * selection, the cursor and a hover still outrank both, as they outrank `BASE`. */
const OVERHANG = new THREE.Color(0xf0b429);
const UNFIT = new THREE.Color(0xd9776c);

/** The bed's floor and the edges of its build volume. */
const FLOOR = 0xaab2bb;
const VOLUME_EDGE = 0x6d8fb3;

/** What a body shown for context is painted, and how much of it: a warm sand no part, no
 * selection and no reference wears, thin enough that the part inside or behind it reads
 * through. It is still shaded, so its shape reads as a body rather than a tint. */
const CONTEXT = new THREE.Color(0xd9b26f);
const CONTEXT_OPACITY = 0.36;

/** The origin, as a constant rather than a fresh vector at every call - every arrow of the
 * datum starts here and nowhere else. */
const ORIGIN = new THREE.Vector3(0, 0, 0);

// The datum's three arms, in the convention a CAD viewport already uses so X-red/Y-green/Z-blue
// needs no legend. Saturated enough to read on both the pane's light and dark gradients - see
// `styles.css`, `.canvas-3d` - which is the same reason the label halo below is white rather
// than picking one text colour for one theme.
const AXIS_X = 0xd6483c;
const AXIS_Y = 0x3c9d52;
const AXIS_Z = 0x3b78c9;
const AXIS_X_CSS = "#d6483c";
const AXIS_Y_CSS = "#3c9d52";
const AXIS_Z_CSS = "#3b78c9";

/** A picked face's frame, task-61's own gizmo: `plane_of`'s X in the datum's own red, so the
 * two read as the same kind of thing, and its normal in a colour neither axis nor selection
 * already uses, so a normal is never mistaken for a stray X axis. */
const FRAME_X = AXIS_X;
const FRAME_NORMAL = 0x9b59d0;

export interface Viewer3D {
  /** Draw these parts - the ones with a body; anything else is not ours to show - standing
   * where the stage says. `sheets` is only read to say which sheet a part is cut from,
   * `reference` is a body somebody else made, stood behind the work and never selectable, and
   * `context` the bodies the script showed for context, drawn translucent where they stand.
   * `bed` is the printer *On bed* lays the printed parts on, and `overhangs` the refs the run's
   * overhang findings name, painted *On bed*. */
  show(
    parts: readonly PartView[],
    stage: StageView,
    sheets: readonly SheetView[],
    reference?: MeshView | null,
    context?: readonly ContextView[],
    bed?: BedView | null,
    overhangs?: readonly string[],
  ): void;
  /** Look at the scene assembled, on the bed or in section - see the module's own note.
   * Untouched by `show()`: a re-run keeps the way of looking, as it keeps the section. The
   * camera frames what the new way shows. *Assembled* by default. */
  mode(mode: ViewMode): void;
  /** Frame everything, and forget that anybody moved the camera. */
  fit(): void;
  /** Turn and zoom to one named place - a finding's (task-94) - from where Python said to
   * stand (`PartView.sights`): its box, looked at along its `eye`, so an underside is seen from
   * underneath. The camera counts as moved, so a re-run leaves it there. Nothing happens for a
   * ref no drawn body carries a sight for, or for a part *On bed* does not lay. */
  frame(ref: string): void;
  /** Dolly in or out about the middle - what the +/- buttons do. */
  zoom(factor: number): void;
  select(ref: string | null): void;
  /** task-61's second pick: shift-click a face on another part. Highlights `ref` alongside
   * whatever `select` last chose, and - when both faces answer to a frame - draws each
   * face's frame as small axes, from the numbers `bench.views` computed. `null` turns the
   * second highlight and both gizmos off without touching the first pick. */
  selectSecond(ref: string | null): void;
  /** Highlight what the editor's cursor is pointing at. */
  point(ref: string | null): void;
  selected(): string | null;
  /** The second pick's ref, or `null` when there is none. */
  selectedSecond(): string | null;
  /** Whether there is anything drawn. */
  empty(): boolean;
  /** Write a line across the view - why there is nothing in it, when there is a part that
   * this run could not build. */
  say(text: string): void;
  /** Colour the backdrop's triangles by which detected flat, if any, each one is - a
   * pastel per flat, generated rather than listed, so the count never runs out - and let
   * the backdrop be clicked while this is on, reporting the flat under the pointer through
   * `onDetectPick`. `null` turns detection off: the backdrop goes back to its plain ghost
   * and stops answering clicks, exactly as before this existed. */
  detect(flatIndex: readonly (number | null)[] | null): void;
  /** Where *Section* cuts: a plane along `axis`, at `position` millimetres in the scene's own
   * coordinates - three.js clipping planes, drawing only, nothing computed here that Python
   * has not already placed. It clips the parts, the reference and the context bodies, and
   * each one's cut face is filled in its own colour - `CUT` for a part - so a gap between two
   * bodies at the section is a gap, not one more shaded surface. It clips only while the mode
   * is *Section*; `null` is no plane at all. Untouched by `show()` - it stays exactly as set
   * across a re-run or a knob change, which is what lets dragging a pose knob sweep the
   * section through the geometry. */
  section(state: SectionState | null): void;
  /** Colour every named face of every built part in its own pastel from the same palette
   * `detect` uses - one index run across every part in the scene, so two faces never share a
   * hue even across a seam between parts. `on` toggles it; off restores the plain base
   * colour. Untouched by `show()` - it survives a re-run exactly the way `chosen` and
   * `pointed` do. Off by default. */
  colourFaces(on: boolean): void;
  /** Light the dropped body up, or put it back to its plain ghost.
   *
   * The backdrop is still never *clickable* outside detection - it answers no raycast, so a
   * click on the work behind it is a click on the work. This is the other direction only: the
   * refs container can say "this one", and the view shows which. While `detect` is on the
   * backdrop is wearing its flats' colours and this does nothing, since being told which body
   * is meant is not a reason to throw away the measurement being looked at. */
  markReference(lit: boolean): void;
  /** Hide every ref in `refs` and everything under it - a part, a node's faces - and show
   * everything else: the refs container's own eye toggles, isolate and show-all all resolve
   * to one call of this, replacing whatever was hidden before. Drawing only: which triangles,
   * segments and lettering answer to a hidden ref is read off the ref membership the scene
   * already carries, nothing computed here that Python did not already name. Untouched by
   * `show()` - it stays exactly as set across a re-run, the same as `section` and
   * `colourFaces` above. Off (nothing hidden) by default. */
  hide(refs: readonly string[]): void;
}

/** Where a click on the backdrop landed, in the dropped body's own coordinates - decision-7's
 * pick, resolved to numbers at the moment of the click and nothing else.
 *
 * `point` is the point the ray actually met; `vertex` is the nearest corner of the triangle it
 * met, which is what a maker clicking "that corner" means on a body whose corner is a vertex.
 * `flatIndex` is the flat those triangles belong to, by the same index `detect`'s own array
 * used, or `null` for a triangle no flat was detected on. */
export interface DetectHit {
  readonly flatIndex: number | null;
  readonly point: readonly [number, number, number];
  readonly vertex: readonly [number, number, number];
}

export interface Viewer3DHooks {
  onSelect(ref: string | null): void;
  /** A shift-click landed on a face of a part different from the one `onSelect`'s ref
   * belongs to - task-61's second pick for *Insert fit*. `ref` is `null` for a shift-click
   * that met nothing; a shift-click that does not qualify (nothing picked first, or the
   * same part again) fires neither hook and leaves the selection exactly as it was. */
  onSelectSecond(ref: string | null): void;
  /** The backdrop was clicked while `detect` was on: where, and which flat - or `null` for a
   * click that met the backdrop nowhere at all. Never fired while detection is off - the
   * backdrop is not listening then. */
  onDetectPick(hit: DetectHit | null): void;
}

/** One part's body on screen: its mesh, the names its triangles are numbered against, and the
 * colours painted on them. */
interface Body {
  readonly mesh: THREE.Mesh;
  readonly refs: readonly string[];
  readonly index: Uint32Array;
  readonly colors: THREE.BufferAttribute;
  readonly part: PartView;
  /** Where *On bed* lays it: Python's placement as a matrix, or `null` for a part that is not
   * laid on the bed - one not printed, or a run with no body or no bed. */
  readonly placement: THREE.Matrix4 | null;
}

/** A body shown for context on screen, numbered and coloured the way a part's is. */
interface Ghost {
  readonly mesh: THREE.Mesh;
  readonly refs: readonly string[];
  readonly index: Uint32Array;
  readonly colors: THREE.BufferAttribute;
  readonly context: ContextView;
}

/** One part's engraved wires on screen, numbered the way a body's triangles are. */
interface Scored {
  readonly lines: THREE.LineSegments;
  readonly refs: readonly string[];
  readonly index: Uint32Array;
  readonly colors: THREE.BufferAttribute;
  readonly part: PartView;
}

/** One line of lettering on screen: its box, the text drawn into it, and its ref. */
interface Lettered {
  readonly quad: THREE.Mesh;
  readonly material: THREE.MeshBasicMaterial;
  readonly texture: THREE.CanvasTexture;
  readonly ref: string | null;
  readonly part: PartView;
}

/** What is under the pointer: the ref it answers to, and the part it belongs to - or, for a
 * face of a body shown for context, `null` and that body. */
interface Found {
  readonly ref: string;
  readonly part: PartView | null;
  readonly context: ContextView | null;
}

/** The entry `at` of a numbered list of refs, or `null` for an entry of no name. */
function refIn(refs: readonly string[], index: Uint32Array, at: number): string | null {
  const place = index[at] ?? 0;
  return place === 0 ? null : (refs[place - 1] ?? null);
}

/** Whether `ref` is `lit` or names something inside it - a face under its part, an edge under
 * its face. Refs are paths, so "inside" is a prefix that ends at a separator. */
function within(ref: string, lit: string | null): boolean {
  return lit !== null && (ref === lit || ref.startsWith(`${lit}/`));
}

/** Whether two references are the same body, by what they are made of rather than by object
 * identity - the wire hands `show()` a freshly built `MeshView` on every run, the same
 * reference included, so two calls with nothing new dropped would look like two different
 * bodies if compared by `===`. */
function sameReference(a: MeshView | null, b: MeshView | null): boolean {
  if (a === null || b === null) return a === b;
  if (a.positions.length !== b.positions.length) return false;
  for (let at = 0; at < a.positions.length; at += 1) {
    if (a.positions[at] !== b.positions[at]) return false;
  }
  return true;
}

/** A part as the second line of the hover tip says it: how many, what it is made of, and the
 * sheets it is cut from. */
function caption(part: PartView, sheets: ReadonlyMap<string, readonly string[]>): string {
  const bits: string[] = [];
  if (part.qty > 1) bits.push(`×${part.qty}`);
  bits.push(
    part.stock.thickness > 0 ? `${part.stock.thickness} mm ${part.stock.material}` : part.stock.material,
  );
  const on = sheets.get(part.ref);
  if (on !== undefined && on.length > 0) bits.push(on.join(", "));
  return bits.join(" · ");
}

/** A single axis letter, always facing the camera, in `color` haloed white so it stays legible
 * on both the pane's light and dark gradients - the halo all but vanishes on the light one,
 * where the colour alone already contrasts, and is what keeps the letter off the dark one's
 * own near-black. */
function axisLabel(text: string, color: string): THREE.Sprite {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const pen = canvas.getContext("2d");
  if (pen !== null) {
    pen.font = `700 ${Math.round(size * 0.62)}px system-ui, sans-serif`;
    pen.textAlign = "center";
    pen.textBaseline = "middle";
    pen.lineWidth = size * 0.2;
    pen.strokeStyle = "#ffffff";
    pen.strokeText(text, size / 2, size / 2 + 1);
    pen.fillStyle = color;
    pen.fillText(text, size / 2, size / 2 + 1);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: texture, depthTest: false, depthWrite: false, transparent: true }),
  );
  sprite.renderOrder = 999;
  return sprite;
}

/** `text` rendered white on nothing, to be tinted by the material it is laid on with. */
function letters(text: string): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  const font = `600 ${LETTER_PX}px system-ui, sans-serif`;
  const pen = canvas.getContext("2d");
  if (pen === null) return canvas;
  pen.font = font;
  canvas.width = Math.max(1, Math.ceil(pen.measureText(text).width));
  canvas.height = LETTER_PX;
  pen.font = font; // resizing a canvas forgets its pen
  pen.fillStyle = "#ffffff";
  pen.textBaseline = "alphabetic";
  pen.fillText(text, 0, LETTER_PX * 0.92);
  return canvas;
}

export function mount(container: HTMLElement, hooks: Viewer3DHooks): Viewer3D {
  const note = document.createElement("div");
  note.className = "canvas-note";
  container.append(note);

  const tip = document.createElement("div");
  tip.className = "canvas-tip";
  tip.hidden = true;
  const tipRef = document.createElement("span");
  const tipPart = document.createElement("span");
  tipPart.className = "canvas-tip-part";
  tip.append(tipRef, tipPart);
  container.append(tip);

  let renderer: THREE.WebGLRenderer | null = null;
  try {
    // `stencil`, which three.js leaves off by default, is what *Section* fills its cut faces with.
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, stencil: true });
  } catch {
    // No WebGL at all - an old browser, a blocked context, a machine with no GPU driver.
    // Everything else still works, so say so here and let the rest of the app carry on.
  }

  if (renderer === null) {
    note.textContent = "this browser has no WebGL, so the parts cannot be drawn; the cut files still export";
    return {
      show: () => {},
      fit: () => {},
      frame: () => {},
      zoom: () => {},
      select: () => {},
      selectSecond: () => {},
      point: () => {},
      selected: () => null,
      selectedSecond: () => null,
      empty: () => true,
      say: () => {},
      detect: () => {},
      mode: () => {},
      section: () => {},
      colourFaces: () => {},
      markReference: () => {},
      hide: () => {},
    };
  }

  const view = renderer;
  view.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  view.domElement.className = "gl";
  container.append(view.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 1, NEAR, FAR);
  camera.up.set(0, 0, 1);

  // Three lights and a sky, because one light makes a part read as a flat blob: a key across
  // the front left, a fill to keep the shadow side from going black, and a low back light that
  // puts a bright edge on every silhouette so shape comes back.
  scene.add(new THREE.HemisphereLight(0xdfe8f2, 0x3c4147, 0.7));
  // Grazing, not overhead: a light straight down makes every top face the same white and a
  // part reads as a paper cut-out. Across and low is what puts a different value on the top,
  // the front and the side of the same box.
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(1.0, -1.15, 0.8);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, 0.55);
  fill.position.set(-1.5, 0.7, 0.35);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.7);
  rim.position.set(0.1, 1.5, -0.75);
  scene.add(rim);

  /** *On bed*'s printer: its floor and the edges of its build volume, both from the numbers
   * `BedView` carries. Drawn in no other mode - an assembly has no bed. */
  const bedGroup = new THREE.Group();
  bedGroup.visible = false;
  scene.add(bedGroup);

  const parts = new THREE.Group();
  scene.add(parts);

  /** *Section*'s cut faces: for each kind of body - the parts, the reference, the context - a
   * pair of stencil passes over its triangles and a quad on the plane that paints only where
   * they counted it open. Out here rather than in `parts` so no raycast ever meets one. */
  const capping = new THREE.Group();
  capping.visible = false;
  scene.add(capping);

  /** The dropped body, if there is one, in a group of its own.
   *
   * Its own rather than `parts` for one reason: picking casts against `parts.children`, and
   * a hit there that answers to nothing would swallow the ray instead of letting it carry on
   * to the part behind. Out here the caster never sees it, so a backdrop cannot be clicked
   * and cannot get in the way of clicking anything else. */
  const backdrop = new THREE.Group();
  scene.add(backdrop);
  let standing: THREE.Mesh | null = null;
  /** Which flat, by index, each triangle of `standing` is under - the same array `detect`
   * was last given, or `null` while detection is off. Kept so a click can be answered
   * without asking the caller to hand the array back, and so the backdrop's own raycast
   * only runs while this is not `null`. */
  let detectedIndex: readonly (number | null)[] | null = null;

  /** Where the origin is and which way X, Y and Z run - the one thing on screen that answers
   * "which way is home" once a dropped body's own coordinates put it hundreds of millimetres
   * from the work. Drawn at the origin itself, not a fixed corner gizmo, because a corner
   * gnomon only ever says which way is up - it cannot say how far off you are.
   *
   * Out here rather than in `parts` for the same reason the backdrop is: picking casts
   * against `parts.children` only, so a click always reaches the face behind the axes instead
   * of stopping on them. */
  const datum = new THREE.Group();
  scene.add(datum);
  const axisX = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), ORIGIN, 1, AXIS_X, 1, 1);
  const axisY = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), ORIGIN, 1, AXIS_Y, 1, 1);
  const axisZ = new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), ORIGIN, 1, AXIS_Z, 1, 1);
  const originDot = new THREE.Mesh(
    new THREE.SphereGeometry(1, 12, 8),
    new THREE.MeshBasicMaterial({ color: 0x808a94, depthTest: false, depthWrite: false }),
  );
  originDot.renderOrder = 998;
  const labelX = axisLabel("X", AXIS_X_CSS);
  const labelY = axisLabel("Y", AXIS_Y_CSS);
  const labelZ = axisLabel("Z", AXIS_Z_CSS);
  datum.add(axisX, axisY, axisZ, originDot, labelX, labelY, labelZ);

  /** Scale the datum to what is in view: fixed at the size a small part needs and it
   * disappears beside a 300 mm handle; scaled to the whole framed box and it moves the moment
   * the scene does, which is the tradeoff and the reason this runs from the same box `fit()`
   * frames from rather than anything measured about a part's own shape. */
  function layDatum(box: THREE.Box3): void {
    const diagonal = box.getSize(new THREE.Vector3()).length();
    const length = Math.max(diagonal * 0.3, 20);
    for (const arrow of [axisX, axisY, axisZ]) arrow.setLength(length, length * 0.12, length * 0.06);
    const dot = Math.max(length * 0.018, 0.5);
    originDot.scale.setScalar(dot);
    const labelAt = length * 1.1;
    labelX.position.set(labelAt, 0, 0);
    labelY.position.set(0, labelAt, 0);
    labelZ.position.set(0, 0, labelAt);
    const labelScale = Math.max(length * 0.16, 4);
    for (const sprite of [labelX, labelY, labelZ]) sprite.scale.setScalar(labelScale);
    // A canvas is one opaque element, same reason `data-bounds` exists: how long the datum's
    // arms are drawn, in millimetres, for a test to read.
    container.dataset["datum"] = length.toFixed(1);
  }

  /** task-61's own gizmo: a picked face's frame, drawn as two small arrows - `plane_of`'s
   * `normal` and `x` - and a dot at its `origin`. Out here beside the datum, not in `parts`,
   * so it is never what a click lands on and a click always reaches the face under it.
   *
   * decision-10's whole reason for drawing this: a face's origin is invisible to somebody
   * clicking it, so what `offset`/`spin` would have to correct is shown at the moment it
   * matters, before *Insert fit* writes anything. */
  const faceFrames = new THREE.Group();
  scene.add(faceFrames);

  /** `ref`'s frame, read off whichever body's `PartView.frames` names it, with that body - or
   * `null` for a ref with none - unpicked, no body drawn for it, or a face `plane_of` could not
   * frame. */
  function frameOf(ref: string | null): { readonly frame: FrameView; readonly body: Body } | null {
    if (ref === null) return null;
    for (const body of bodies) {
      const found = body.part.frames[ref];
      if (found !== undefined) return { frame: found, body };
    }
    return null;
  }

  /** The part ``ref`` belongs to, or `null` for a ref no body drawn now answers to - what a
   * shift-click compares the first pick's ref against, to tell "a face on another part" from
   * "the same part again". */
  function partRefOf(ref: string): string | null {
    const body = bodies.find((one) => one.part.ref === ref || one.refs.includes(ref));
    return body?.part.ref ?? null;
  }

  function frameGizmo(at: FrameView, length: number): THREE.Group {
    const group = new THREE.Group();
    const origin = new THREE.Vector3(...at.origin);
    const x = new THREE.ArrowHelper(
      new THREE.Vector3(...at.x).normalize(),
      origin,
      length,
      FRAME_X,
      length * 0.28,
      length * 0.16,
    );
    const normal = new THREE.ArrowHelper(
      new THREE.Vector3(...at.normal).normalize(),
      origin,
      length,
      FRAME_NORMAL,
      length * 0.28,
      length * 0.16,
    );
    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(Math.max(length * 0.06, 0.3), 10, 8),
      new THREE.MeshBasicMaterial({ color: FRAME_NORMAL, depthTest: false, depthWrite: false }),
    );
    dot.position.copy(origin);
    for (const one of [x, normal, dot]) one.renderOrder = 997;
    group.add(x, normal, dot);
    return group;
  }

  /** Redraw the gizmos for whatever `chosen` and `chosenSecond` currently answer to - never
   * cached, since a new `show()` can bring a different frame for the same ref. */
  function layFaceFrames(): void {
    for (const child of [...faceFrames.children]) {
      faceFrames.remove(child);
      if (!(child instanceof THREE.Group)) continue;
      for (const part of child.children) {
        // `ArrowHelper`'s own line and cone geometry are shared across every instance three.js
        // makes, so only its per-instance material is ever this gizmo's to dispose; the dot is
        // a plain mesh and owns both.
        if (part instanceof THREE.ArrowHelper) {
          if (part.line.material instanceof THREE.Material) part.line.material.dispose();
          if (part.cone.material instanceof THREE.Material) part.cone.material.dispose();
        } else if (part instanceof THREE.Mesh) {
          part.geometry.dispose();
          if (part.material instanceof THREE.Material) part.material.dispose();
        }
      }
    }
    const diagonal = bounds.getSize(new THREE.Vector3()).length();
    const length = Math.max(diagonal * 0.12, 8);
    let drawn = 0;
    for (const ref of [chosen, chosenSecond]) {
      const found = frameOf(ref);
      if (found === null || !found.body.mesh.visible) continue;
      const gizmo = frameGizmo(found.frame, length);
      // A frame is where its face is drawn, so *On bed* it goes where its body went - by the
      // body's own matrix, the one Python sent, and no other.
      gizmo.matrixAutoUpdate = false;
      gizmo.matrix.copy(found.body.mesh.matrix);
      faceFrames.add(gizmo);
      drawn += 1;
    }
    // For a test to read, the "for a test to read" convention `data-bodies` etc already use:
    // how many of the up-to-two picked faces actually drew a frame.
    container.dataset["frames"] = String(drawn);
  }

  const controls = new OrbitControls(camera, view.domElement);
  controls.enableDamping = false;
  controls.addEventListener("change", () => {
    // `fit` moves the camera too, and its `update` raises this - so without the guard the
    // view would count itself as hand-moved the first time it framed anything, and never
    // frame a new scene again.
    if (!fitting) touched = true;
    draw();
  });

  let bodies: Body[] = [];
  /** The bodies shown for context - apart from `bodies`, so what counts, colours and hides
   * parts never counts, colours or hides one. */
  let ghosts: Ghost[] = [];
  let scored: Scored[] = [];
  let lettered: Lettered[] = [];
  let sheetsOf: ReadonlyMap<string, readonly string[]> = new Map();
  let bounds = new THREE.Box3(new THREE.Vector3(-50, -50, 0), new THREE.Vector3(50, 50, 50));
  layDatum(bounds); // sized once up front, so the datum has a sane scale before the first `show()`
  let touched = false;
  /** The reference `show()` last drew, kept to tell "a new body arrived" from "the scene was
   * redrawn": every run resends the same reference along with the work, freshly deserialised,
   * so this is compared by content, never by identity. */
  let referenceDrawn: MeshView | null = null;
  /** Set while `fit` is moving the camera itself, so its own `change` is not a person's. */
  let fitting = false;
  let chosen: string | null = null;
  /** task-61's second pick: a shift-click's ref, on a part `chosen` is not on, or `null`. */
  let chosenSecond: string | null = null;
  let pointed: string | null = null;
  let hovered: string | null = null;
  let frame = 0;

  // ---- the way of looking, and the section ------------------------------------------
  //
  // One plane, shared by every clipped material - moving it moves every body's section at
  // once, and is the only thing changing it ever does, so no material is rebuilt when the
  // axis, the position or the mode changes. Clipping is enabled or disabled for the whole
  // renderer instead of by emptying `clippingPlanes`, which is what keeps a change of mode
  // from asking three.js to recompile every part's shader.
  view.localClippingEnabled = false;
  const clipPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
  let section: SectionState | null = null;
  let look: ViewMode = "assembled";
  /** The box *Assembled* and *Section* frame - the stage, and a reference beside it - and the
   * one *On bed* frames, the bed and everything on it; `bounds` is whichever is on screen. */
  let stageBox = new THREE.Box3(new THREE.Vector3(-50, -50, 0), new THREE.Vector3(50, 50, 50));
  let bedBox: THREE.Box3 | null = null;
  /** The refs the run's overhang findings name - painted *On bed*. */
  let overhanging: ReadonlySet<string> = new Set();

  function planeFor(state: SectionState): void {
    switch (state.axis) {
      case "x":
        clipPlane.normal.set(-1, 0, 0);
        clipPlane.constant = state.position;
        break;
      case "y":
        clipPlane.normal.set(0, 1, 0);
        clipPlane.constant = -state.position;
        break;
      case "z":
        clipPlane.normal.set(0, 0, -1);
        clipPlane.constant = state.position;
        break;
    }
  }

  /** One kind of body's cut face. Every surface of the kind is drawn twice more, into the
   * stencil only and clipped like the body: its back faces counting up, its front faces down,
   * so a pixel whose count is not zero is one where the plane passes through the inside of a
   * closed body. The quad on the plane then paints exactly those pixels, depth-tested so a
   * part in front still hides it, and puts the count back to zero as it goes, ready for the
   * next kind. `order` keeps each kind's passes and quad together and in turn. */
  interface Capper {
    readonly back: THREE.Material;
    readonly front: THREE.Material;
    readonly quad: THREE.Mesh;
    readonly order: number;
  }

  function stencilPass(side: THREE.Side, op: THREE.StencilOp): THREE.MeshBasicMaterial {
    return new THREE.MeshBasicMaterial({
      side,
      colorWrite: false,
      depthWrite: false,
      depthTest: false,
      stencilWrite: true,
      stencilFunc: THREE.AlwaysStencilFunc,
      stencilFail: op,
      stencilZFail: op,
      stencilZPass: op,
      clippingPlanes: [clipPlane],
    });
  }

  /** The stencil passes, one pair per body, rebuilt with the bodies; the quads outlive them. */
  const passes = new THREE.Group();
  capping.add(passes);

  function capper(colour: THREE.Color, order: number): Capper {
    const quad = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({
        color: colour,
        side: THREE.DoubleSide,
        stencilWrite: true,
        stencilRef: 0,
        stencilFunc: THREE.NotEqualStencilFunc,
        stencilFail: THREE.ReplaceStencilOp,
        stencilZFail: THREE.ReplaceStencilOp,
        stencilZPass: THREE.ReplaceStencilOp,
      }),
    );
    quad.renderOrder = order + 1;
    capping.add(quad);
    return {
      back: stencilPass(THREE.BackSide, THREE.IncrementWrapStencilOp),
      front: stencilPass(THREE.FrontSide, THREE.DecrementWrapStencilOp),
      quad,
      order,
    };
  }

  const partCaps = capper(CUT, 1);
  const referenceCaps = capper(REFERENCE_CUT, 3);
  const contextCaps = capper(CONTEXT_CUT, 5);

  /** Count `geometry`'s surfaces into `kind`'s cut face - two more meshes over the same
   * buffer, so a body hidden by the refs container is hidden from its count as well. */
  function counted(geometry: THREE.BufferGeometry, kind: Capper): void {
    for (const material of [kind.back, kind.front]) {
      const pass = new THREE.Mesh(geometry, material);
      pass.renderOrder = kind.order;
      passes.add(pass);
    }
  }

  /** Stand each kind's quad on the plane, big enough to cover everything it could cut - the
   * plane's own axis and position, and the middle of the stage, and nothing measured. */
  function layCaps(state: SectionState): void {
    const size = stageBox.getSize(new THREE.Vector3()).length() * 2 + 10;
    const middle = stageBox.getCenter(new THREE.Vector3());
    for (const { quad } of [partCaps, referenceCaps, contextCaps]) {
      quad.scale.set(size, size, 1);
      quad.rotation.set(0, 0, 0);
      switch (state.axis) {
        case "x":
          quad.rotation.y = Math.PI / 2;
          quad.position.set(state.position, middle.y, middle.z);
          break;
        case "y":
          quad.rotation.x = Math.PI / 2;
          quad.position.set(middle.x, state.position, middle.z);
          break;
        case "z":
          quad.position.set(middle.x, middle.y, state.position);
          break;
      }
    }
  }

  /** Put the view back to what `look` and `section` say: which bodies are drawn, where each
   * one stands, what is clipped and what is framed. Everything it changes is visibility, a
   * matrix Python sent, or the plane - so it costs nothing to run on every change. */
  function applyLook(): void {
    const onBed = look === "bed";
    const cutting = look === "section" && section !== null;
    if (section !== null) planeFor(section);
    view.localClippingEnabled = cutting;
    capping.visible = cutting;
    if (cutting && section !== null) layCaps(section);
    bedGroup.visible = onBed;
    container.dataset["floor"] = onBed && bedGroup.children.length > 0 ? "on" : "";
    let unfit = 0;
    for (const body of bodies) {
      const laid = onBed ? body.placement : null;
      body.mesh.visible = !onBed || laid !== null;
      if (laid === null) body.mesh.matrix.identity();
      else body.mesh.matrix.copy(laid);
      body.mesh.matrixWorldNeedsUpdate = true;
      if (laid !== null && body.part.printing?.fits === false) unfit += 1;
    }
    for (const one of scored) one.lines.visible = !onBed;
    for (const one of lettered) one.quad.visible = !onBed && !isHidden(one.ref ?? one.part.ref);
    for (const ghost of ghosts) ghost.mesh.visible = !onBed;
    backdrop.visible = !onBed;
    bounds = onBed && bedBox !== null ? bedBox : stageBox;
    layDatum(bounds);
    scene.updateMatrixWorld();
    container.dataset["mode"] = look;
    container.dataset["section"] =
      cutting && section !== null ? `${section.axis}:${section.position.toFixed(2)}` : "";
    container.dataset["unfit"] = String(unfit);
    paint();
  }

  function applySection(state: SectionState | null): void {
    section = state;
    applyLook();
  }

  function applyMode(next: ViewMode): void {
    const reframe = (next === "bed") !== (look === "bed");
    look = next;
    applyLook();
    // On and off the bed the work stands somewhere else, so the camera goes to it; between
    // *Assembled* and *Section* nothing moved, and a camera aimed at a cut stays aimed.
    if (reframe) {
      touched = false;
      fit();
    }
  }

  // ---- colour faces -----------------------------------------------------------------
  //
  // Which pastel each named face is painted, one index run across every body in the scene so
  // two faces never land on the same hue even across a seam between parts - the same
  // `pastels()` `detect` already uses below, kept in step by `show()` rebuilding it from the
  // refs each body actually carries. `colouring` is the toggle; it is not reset by `clear()`,
  // so it survives a re-run exactly the way `chosen` and `pointed` do.
  let colouring = false;
  let faceColour: ReadonlyMap<string, THREE.Color> = new Map();

  // ---- hide/show --------------------------------------------------------------------
  //
  // Which rows the refs container has hidden, by their own exact ref path. "Hides everything
  // under it" is `within` at the moment triangles are filtered - the same prefix check
  // `shade()` already reads `chosen` and `flagged` by - so hiding a part never has to expand
  // into the hundreds of face refs under it. Kept in the closure, not sent anywhere:
  // decision-7 is about a pick; this is view state exactly as `section` and `colouring`
  // above are, and untouched by `clear()`, so a re-run keeps it.
  let hiddenRefs: readonly string[] = [];

  const isHidden = (ref: string): boolean => hiddenRefs.some((root) => within(ref, root));

  /** `refs`/`index` filtered to only the entries (triangles at `step` 3, segments at `step`
   * 2) whose own ref is not hidden, as the vertex numbers into `positions` an indexed
   * `BufferGeometry` wants - or `null` when nothing is hidden, which puts the geometry back
   * to its plain, non-indexed form rather than an index that names every entry.
   *
   * This is the one rebuild hiding costs: once per toggle, over however many triangles the
   * scene actually has - never once per frame, and never once per ref. `hiddenRefs` is
   * ordinarily a handful of rows a person clicked, so the cost here is the scene's own
   * triangle count, read once, which is what stays cheap on the cabinet's 770 refs: the tree
   * has 770 names, but a toggle still costs one pass over the triangles, not the names. */
  function filteredIndex(
    refs: readonly string[],
    index: Uint32Array,
    fallback: string,
    step: number,
  ): THREE.BufferAttribute | null {
    if (hiddenRefs.length === 0) return null;
    const kept: number[] = [];
    for (let at = 0; at < index.length; at += 1) {
      if (isHidden(refIn(refs, index, at) ?? fallback)) continue;
      for (let corner = 0; corner < step; corner += 1) kept.push(at * step + corner);
    }
    return new THREE.BufferAttribute(new Uint32Array(kept), 1);
  }

  /** Put every body, engraved wire and line of lettering back to what `hiddenRefs` now says.
   *
   * The index rebuilt here is what keeps a hidden triangle both undrawn and unpickable in one
   * move: three.js's own raycast against a `Mesh` or `LineSegments` walks the index when
   * there is one, so an entry left out of it is never tested, the same way a section's own
   * clip plane is filtered in `under()` below - except this needs no per-hit test at all,
   * because the geometry itself no longer carries what is hidden. */
  function applyHidden(): void {
    for (const body of bodies) {
      body.mesh.geometry.setIndex(filteredIndex(body.refs, body.index, body.part.ref, 3));
    }
    for (const one of scored) {
      one.lines.geometry.setIndex(filteredIndex(one.refs, one.index, one.part.ref, 2));
    }
    for (const one of lettered) one.quad.visible = look !== "bed" && !isHidden(one.ref ?? one.part.ref);
    // For a test to read, the same "for a test to read" convention `data-bodies` etc already
    // use: how many triangles across every body are hidden right now.
    let hidden = 0;
    for (const body of bodies) {
      for (let at = 0; at < body.index.length; at += 1) {
        if (isHidden(refIn(body.refs, body.index, at) ?? body.part.ref)) hidden += 1;
      }
    }
    container.dataset["hidden"] = String(hidden);
    paint();
  }

  /** Draw once, on the next frame; several changes in one tick cost one picture. */
  function draw(): void {
    container.dataset["distance"] = camera.position.distanceTo(controls.target).toFixed(1);
    const eye = camera.position.clone().sub(controls.target).normalize();
    container.dataset["eye"] = [eye.x, eye.y, eye.z].map((one) => one.toFixed(2)).join(",");
    if (frame !== 0) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const rect = container.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) return;
      view.setSize(rect.width, rect.height, false);
      camera.aspect = rect.width / rect.height;
      camera.updateProjectionMatrix();
      view.render(scene, camera);
    });
  }

  /** The colour for something answering to `ref`, drawn in `base` when nothing lights it.
   *
   * A ref lights up what it names and everything under it: `drawer-front-1` is the whole
   * plate, `drawer-front-1/pull` only the pull's wall. And what has no name of its own - the
   * top of a plate whose face is unnamed - answers to its part, as a click on it does, so
   * selecting it lights it. Priority in that order: a selected face stays selected while the
   * pointer wanders over it, and the editor's cursor beats a hover because it is the thing
   * being typed. */
  function shade(ref: string, base: THREE.Color): THREE.Color {
    if (within(ref, chosen)) return SELECTED;
    if (within(ref, chosenSecond)) return SELECTED;
    if (within(ref, pointed)) return CURSOR;
    if (within(ref, hovered)) return HOVER;
    return base;
  }

  /** Put every colour back from what is selected, pointed at and hovered - and, while
   * `colouring` is on, from which named face a triangle is under, so a click or a hover still
   * outranks its own face colour exactly as it outranks the plain `BASE` it usually stands
   * on. */
  function paint(): void {
    let lit = 0;
    let overhang = 0;
    const onBed = look === "bed";
    for (const body of bodies) {
      const unfit = onBed && body.part.printing?.fits === false;
      for (let triangle = 0; triangle < body.index.length; triangle += 1) {
        const ref = refIn(body.refs, body.index, triangle);
        let base = colouring && ref !== null ? (faceColour.get(ref) ?? BASE) : BASE;
        // *On bed*, what a printer will have trouble with outranks a face's own colour: an
        // overhang the run found, then a part too big for the bed.
        if (onBed && ref !== null && overhanging.has(ref)) {
          base = OVERHANG;
          overhang += 1;
        } else if (unfit) base = UNFIT;
        const colour = shade(ref ?? body.part.ref, base);
        if (colour === SELECTED) lit += 1;
        for (let corner = 0; corner < 3; corner += 1) {
          body.colors.setXYZ(3 * triangle + corner, colour.r, colour.g, colour.b);
        }
      }
      body.colors.needsUpdate = true;
    }
    for (const one of scored) {
      for (let segment = 0; segment < one.index.length; segment += 1) {
        const colour = shade(refIn(one.refs, one.index, segment) ?? one.part.ref, INK);
        one.colors.setXYZ(2 * segment, colour.r, colour.g, colour.b);
        one.colors.setXYZ(2 * segment + 1, colour.r, colour.g, colour.b);
      }
      one.colors.needsUpdate = true;
    }
    for (const one of lettered) one.material.color.copy(shade(one.ref ?? one.part.ref, INK));
    for (const ghost of ghosts) {
      for (let triangle = 0; triangle < ghost.index.length; triangle += 1) {
        // A triangle of no name answers to nothing, so nothing lights it.
        const ref = refIn(ghost.refs, ghost.index, triangle);
        const colour = ref === null ? CONTEXT : shade(ref, CONTEXT);
        for (let corner = 0; corner < 3; corner += 1) {
          ghost.colors.setXYZ(3 * triangle + corner, colour.r, colour.g, colour.b);
        }
      }
      ghost.colors.needsUpdate = true;
    }
    container.dataset["selected"] = chosen ?? "";
    container.dataset["second"] = chosenSecond ?? "";
    container.dataset["pointed"] = pointed ?? "";
    container.dataset["lit"] = String(lit);
    container.dataset["overhang"] = String(overhang);
    layFaceFrames();
    container.dataset["colourFaces"] = colouring ? "on" : "";
    draw();
  }

  function clear(): void {
    for (const body of bodies) {
      // The section's stencil passes share this geometry and the cappers' materials, so the
      // geometry goes once, here, and the passes are only let go of below.
      body.mesh.geometry.dispose();
      const material = body.mesh.material;
      if (material instanceof THREE.Material) material.dispose();
    }
    for (const one of scored) {
      one.lines.geometry.dispose();
      const material = one.lines.material;
      if (material instanceof THREE.Material) material.dispose();
    }
    for (const one of lettered) {
      one.quad.geometry.dispose();
      one.material.dispose();
      one.texture.dispose();
    }
    for (const ghost of ghosts) {
      ghost.mesh.geometry.dispose();
      const material = ghost.mesh.material;
      if (material instanceof THREE.Material) material.dispose();
    }
    if (standing !== null) {
      standing.geometry.dispose();
      const material = standing.material;
      if (material instanceof THREE.Material) material.dispose();
      standing = null;
    }
    detectedIndex = null;
    backdrop.clear();
    parts.clear();
    passes.clear();
    for (const child of bedGroup.children) {
      if (child instanceof THREE.LineSegments) {
        child.geometry.dispose();
        if (child.material instanceof THREE.Material) child.material.dispose();
      }
    }
    bedGroup.clear();
    bodies = [];
    ghosts = [];
    scored = [];
    lettered = [];
  }

  const GHOST_COLOR = 0x8d94a0;
  const GHOST_OPACITY = 0.28;
  const DETECT_OPACITY = 0.92;
  /** Lit, a ghost is still a ghost - it stands behind the work and must not start reading as
   * one of the parts. So it keeps `SELECTED`'s hue and gains enough body to be unmistakable,
   * rather than going opaque. */
  const MARKED_OPACITY = 0.55;

  /** Whether the refs container has said this body is the one meant. */
  let marked = false;

  /** Put the backdrop's own colour back from `marked`. Does nothing while detection is on:
   * the flats' colours are vertex colours and are what a person is reading then. */
  function paintReference(): void {
    if (standing === null || detectedIndex !== null) return;
    const material = standing.material;
    if (!(material instanceof THREE.MeshStandardMaterial)) return;
    material.color.set(marked ? SELECTED : GHOST_COLOR);
    material.opacity = marked ? MARKED_OPACITY : GHOST_OPACITY;
    container.dataset["reference"] = marked ? "marked" : "";
    draw();
  }

  function markReference(lit: boolean): void {
    marked = lit;
    paintReference();
  }

  /** Stand a dropped body behind the work: ghosted, so the parts read in front of it, and
   * written into the depth buffer as normal so it occludes honestly rather than floating. */
  function stand(positions: Float32Array): void {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.computeVertexNormals();
    standing = new THREE.Mesh(
      geometry,
      new THREE.MeshStandardMaterial({
        color: GHOST_COLOR,
        roughness: 0.9,
        metalness: 0.0,
        flatShading: true,
        transparent: true,
        opacity: GHOST_OPACITY,
        depthWrite: false,
        side: THREE.DoubleSide,
        clippingPlanes: [clipPlane],
      }),
    );
    backdrop.add(standing);
    counted(geometry, referenceCaps);
    // A run redraws the same body on every keystroke, and a mesh built here starts plain -
    // so a body that was lit before the redraw is lit again after it.
    paintReference();
  }

  /** ``count`` pastels, evenly spaced round the hue wheel at one saturation and one
   * lightness - generated rather than listed, so detecting fifty flats reads as coordinated
   * as detecting five, and a mesh with more flats than any fixed list held never runs out. */
  /** The golden angle, turns rather than radians: stepping a hue by this, again and again,
   * never repeats and never lands two steps close together - unlike `i / count`, which
   * would put flat 0 and flat 1 a 579th of the wheel apart on a mesh with 579 of them, and
   * flats are sorted biggest first, so the two flats most likely to sit side by side on a
   * real part are exactly the two whose indices are closest. */
  const GOLDEN_TURN = 0.618033988749895;

  function pastels(count: number): THREE.Color[] {
    const found: THREE.Color[] = [];
    for (let i = 0; i < count; i++) {
      const hue = (i * GOLDEN_TURN) % 1;
      found.push(new THREE.Color().setHSL(hue, 0.45, 0.74));
    }
    return found;
  }

  /** Colour `standing`'s triangles by `flatIndex`, or put it back to its plain ghost when
   * `flatIndex` is `null`. The array is triangle for triangle against `standing`'s own
   * position buffer - three vertices in a row per triangle, painted the same colour so flat
   * shading reads one colour per face rather than a gradient across it. */
  function detect(flatIndex: readonly (number | null)[] | null): void {
    detectedIndex = flatIndex;
    if (standing === null) return;
    const material = standing.material as THREE.MeshStandardMaterial;
    if (flatIndex === null) {
      standing.geometry.deleteAttribute("color");
      material.vertexColors = false;
      material.needsUpdate = true;
      // Back to plain, or back to lit: turning detection off is not a reason to forget that
      // the refs container has this body selected.
      paintReference();
      return;
    }
    let flats = 0;
    for (const one of flatIndex) if (one !== null && one + 1 > flats) flats = one + 1;
    const palette = pastels(Math.max(flats, 1));
    const neutral = new THREE.Color(GHOST_COLOR);
    const triangles = standing.geometry.getAttribute("position").count / 3;
    const colors = new Float32Array(triangles * 9);
    for (let t = 0; t < triangles; t++) {
      const one = t < flatIndex.length ? (flatIndex[t] ?? null) : null;
      const color = one === null ? neutral : (palette[one] ?? neutral);
      for (let v = 0; v < 3; v++) {
        const at = (t * 3 + v) * 3;
        colors[at] = color.r;
        colors[at + 1] = color.g;
        colors[at + 2] = color.b;
      }
    }
    standing.geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    material.vertexColors = true;
    material.color.setHex(0xffffff);
    material.opacity = DETECT_OPACITY;
    material.needsUpdate = true;
    draw();
  }

  /** Where on the backdrop the pointer is and which flat is there, or `null` for a click that
   * met it nowhere - only asked while `detectedIndex` is not `null`, which is the backdrop's
   * own permission to be clicked at all.
   *
   * Both points come back in the backdrop's own coordinates, which are the dropped body's own:
   * `intersectObject` answers in world space, so the hit is taken back through the mesh's own
   * matrix rather than trusted to be the same numbers - decision-7's pick writes the mesh's
   * numbers, and a group somebody moves later must not quietly change what they say. */
  function detectedAt(event: PointerEvent): DetectHit | null {
    if (detectedIndex === null || standing === null) return null;
    const rect = view.domElement.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    where.set(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    caster.setFromCamera(where, camera);
    const hit = caster.intersectObject(standing, false)[0];
    if (hit === undefined) return null;
    const triangle = hit.faceIndex ?? -1;
    const flatIndex =
      triangle >= 0 && triangle < detectedIndex.length ? (detectedIndex[triangle] ?? null) : null;
    const local = standing.worldToLocal(hit.point.clone());
    const point: readonly [number, number, number] = [local.x, local.y, local.z];
    return { flatIndex, point, vertex: cornerNearest(local, hit) };
  }

  /** The corner of the triangle `hit` met that is nearest `local` - in the same coordinates,
   * since a geometry's own position attribute already holds them. The whole point of offering
   * it beside the hit: on a body whose corner is a vertex, this *is* that corner, to the last
   * float the exporter wrote, where the point the ray met is only somewhere near it. */
  function cornerNearest(
    local: THREE.Vector3,
    hit: THREE.Intersection,
  ): readonly [number, number, number] {
    const face = hit.face;
    const positions = standing?.geometry.getAttribute("position");
    if (face === null || face === undefined || positions === undefined) {
      return [local.x, local.y, local.z];
    }
    let best: readonly [number, number, number] = [local.x, local.y, local.z];
    let away = Number.POSITIVE_INFINITY;
    for (const at of [face.a, face.b, face.c]) {
      const corner: readonly [number, number, number] = [
        positions.getX(at),
        positions.getY(at),
        positions.getZ(at),
      ];
      const span = Math.hypot(corner[0] - local.x, corner[1] - local.y, corner[2] - local.z);
      if (span < away) {
        away = span;
        best = corner;
      }
    }
    return best;
  }

  function bodyOf(part: PartView, positions: Float32Array, refs: readonly string[], index: Uint32Array): Body {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const colors = new THREE.BufferAttribute(new Float32Array(positions.length), 3);
    geometry.setAttribute("color", colors);
    geometry.computeVertexNormals();
    const surface = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.62,
      metalness: 0.04,
      flatShading: true,
      clippingPlanes: [clipPlane],
    });
    const mesh = new THREE.Mesh(geometry, surface);
    // Where it stands is set by `applyLook` alone - nowhere, or Python's placement *On bed* -
    // so three.js is never asked to work a matrix out of a position and a rotation.
    mesh.matrixAutoUpdate = false;
    parts.add(mesh);
    counted(geometry, partCaps);
    const rows = part.printing?.placement ?? null;
    const placement =
      rows === null
        ? null
        : new THREE.Matrix4().set(
            ...(rows as [number, number, number, number, number, number, number, number, number, number, number, number]),
            0,
            0,
            0,
            1,
          );
    return { mesh, refs, index, colors, part, placement };
  }

  /** A body shown for context: vertex-coloured like a part's so its faces can light, and
   * translucent, writing no depth so the parts inside and behind it draw through. */
  function ghostOf(context: ContextView, mesh: MeshView): Ghost {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(mesh.positions, 3));
    const colors = new THREE.BufferAttribute(new Float32Array(mesh.positions.length), 3);
    geometry.setAttribute("color", colors);
    geometry.computeVertexNormals();
    const surface = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.8,
      metalness: 0.0,
      flatShading: true,
      transparent: true,
      opacity: CONTEXT_OPACITY,
      depthWrite: false,
      side: THREE.DoubleSide,
      clippingPlanes: [clipPlane],
    });
    const drawn = new THREE.Mesh(geometry, surface);
    parts.add(drawn);
    counted(geometry, contextCaps);
    return { mesh: drawn, refs: mesh.refs, index: mesh.ref_index, colors, context };
  }

  function scoredOf(part: PartView, marks: MarksView): Scored {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(marks.segments, 3));
    const colors = new THREE.BufferAttribute(new Float32Array(marks.segments.length), 3);
    geometry.setAttribute("color", colors);
    const drawn = new THREE.LineSegments(
      geometry,
      new THREE.LineBasicMaterial({ vertexColors: true, clippingPlanes: [clipPlane] }),
    );
    parts.add(drawn);
    return { lines: drawn, refs: marks.refs, index: marks.ref_index, colors, part };
  }

  function letteredOf(part: PartView, one: LetteringView): Lettered {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(one.corners), 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]), 2));
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
    const texture = new THREE.CanvasTexture(letters(one.text));
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      clippingPlanes: [clipPlane],
    });
    const quad = new THREE.Mesh(geometry, material);
    parts.add(quad);
    return { quad, material, texture, ref: one.ref, part };
  }

  function show(
    given: readonly PartView[],
    stage: StageView,
    sheets: readonly SheetView[],
    reference: MeshView | null = null,
    context: readonly ContextView[] = [],
    bed: BedView | null = null,
    overhangs: readonly string[] = [],
  ): void {
    clear();
    overhanging = new Set(overhangs);
    if (reference !== null && reference.positions.length > 0) stand(reference.positions);
    const on = new Map<string, string[]>();
    for (const sheet of sheets) {
      for (const ref of sheet.parts) {
        const names = on.get(ref) ?? [];
        if (!names.includes(sheet.name)) names.push(sheet.name);
        on.set(ref, names);
      }
    }
    sheetsOf = on;
    for (const part of given) {
      const mesh = part.mesh;
      if (mesh === null || mesh.ref_index.length === 0) continue;
      bodies.push(bodyOf(part, mesh.positions, mesh.refs, mesh.ref_index));
      if (part.marks !== null) scored.push(scoredOf(part, part.marks));
      for (const one of part.lettering) lettered.push(letteredOf(part, one));
    }
    for (const one of context) {
      if (one.mesh === null || one.mesh.ref_index.length === 0) continue;
      ghosts.push(ghostOf(one, one.mesh));
    }

    // One palette index across the whole scene, in the order its faces are met - a part's own
    // faces stay together in that order, which is exactly where two faces are most likely to
    // be neighbours, so `pastels`' golden-angle step keeps them apart the same way `detect`
    // already relies on it to.
    const named: string[] = [];
    const seen = new Set<string>();
    for (const body of bodies) {
      for (let triangle = 0; triangle < body.index.length; triangle += 1) {
        const ref = refIn(body.refs, body.index, triangle);
        if (ref !== null && !seen.has(ref)) {
          seen.add(ref);
          named.push(ref);
        }
      }
    }
    const facePalette = pastels(Math.max(named.length, 1));
    faceColour = new Map(named.map((ref, at) => [ref, facePalette[at] ?? BASE]));

    const [x0 = -50, y0 = -50, z0 = 0, x1 = 50, y1 = 50, z1 = 50] = stage.bounds;
    stageBox = new THREE.Box3(new THREE.Vector3(x0, y0, z0), new THREE.Vector3(x1, y1, z1));
    // The stage measures the work, and a dropped body is not part of it - but if somebody
    // dropped it they meant to look at it, and a backdrop framed out of view or drawn as a
    // speck in the corner is the same as one that never arrived. So the view is framed round
    // both, at the cost of the work reading smaller beside a large reference.
    if (standing !== null) {
      standing.geometry.computeBoundingBox();
      const around = standing.geometry.boundingBox;
      if (around !== null) stageBox.union(around);
    }
    // Origin included too, always - the datum's whole point is showing where it sits relative
    // to the work, which a box that only ever covered the work could not do the one time that
    // question matters: everything sits hundreds of millimetres from a dropped body's origin.
    stageBox.expandByPoint(ORIGIN);
    bedBox = layBed(bed);
    container.dataset["bodies"] = String(bodies.length);
    container.dataset["triangles"] = String(bodies.reduce((sum, one) => sum + one.index.length, 0));
    container.dataset["bounds"] = stage.bounds.join(",");
    container.dataset["context"] = String(ghosts.length);
    container.dataset["contextTriangles"] = String(
      ghosts.reduce((sum, one) => sum + one.index.length, 0),
    );
    container.dataset["bed"] = bed === null ? "" : (bed.printer ?? bed.volume.join(" x "));
    container.dataset["plates"] = String(bed?.plates ?? 0);
    container.dataset["laid"] = String(bodies.filter((one) => one.placement !== null).length);

    // A selected or pointed-at ref the new scene no longer has is dropped, and the host is
    // told, so the status bar does not keep offering a name nothing answers to.
    const lost = chosen !== null && !known(chosen);
    if (lost) chosen = null;
    const lostSecond = chosenSecond !== null && !known(chosenSecond);
    if (lostSecond) chosenSecond = null;
    if (pointed !== null && !known(pointed)) pointed = null;
    hovered = null;
    // Every body, wire and quad above is freshly built, standing nowhere and plain, so where
    // the way of looking puts it and what `hiddenRefs` says have to be put back on it - the
    // same reason `stand()` repaints a lit reference on every redraw. `applyHidden` is what
    // paints, so nothing here calls `paint()` a third time.
    applyLook();
    applyHidden();
    if (lost) hooks.onSelect(null);
    if (lostSecond) hooks.onSelectSecond(null);
    // A dropped body is worth framing even when the script made nothing to stand beside it,
    // which is exactly the case where somebody is measuring before they have written much.
    //
    // A run redraws the same reference on every keystroke, and must not yank a camera the
    // maker has aimed - that is what `touched` guards. But a drop is not a run: it is a
    // deliberate "look at this", so it frames even when `touched`, and that includes dropping
    // a different file over an existing reference (the same deliberate act again) and
    // clearing one (the reference leaves, so the frame goes back to the work). What must never
    // move is the mesh itself - only the camera.
    const arrived = !sameReference(reference, referenceDrawn);
    referenceDrawn = reference;
    const something = bodies.length > 0 || ghosts.length > 0 || standing !== null || bedBox !== null;
    if (arrived || (!touched && something)) fit();
    else draw();
  }

  const known = (ref: string): boolean =>
    bodies.some((one) => one.part.ref === ref || one.refs.includes(ref)) ||
    scored.some((one) => one.refs.includes(ref)) ||
    lettered.some((one) => one.ref === ref) ||
    ghosts.some((one) => one.refs.includes(ref));

  /** The printer's plates - each one's floor and build volume, line segments Python placed -
   * drawn into `bedGroup`, and the box *On bed* frames; `null` when no printer was named. */
  function layBed(bed: BedView | null): THREE.Box3 | null {
    if (bed === null) return null;
    const lines = (segments: readonly number[], material: THREE.LineBasicMaterial): THREE.LineSegments => {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(segments), 3));
      return new THREE.LineSegments(geometry, material);
    };
    bedGroup.add(
      lines(bed.floor, new THREE.LineBasicMaterial({ color: FLOOR, transparent: true, opacity: 0.6 })),
      lines(bed.edges, new THREE.LineBasicMaterial({ color: VOLUME_EDGE })),
    );
    const [x0 = 0, y0 = 0, z0 = 0, x1 = 0, y1 = 0, z1 = 0] = bed.bounds;
    return new THREE.Box3(new THREE.Vector3(x0, y0, z0), new THREE.Vector3(x1, y1, z1)).expandByPoint(ORIGIN);
  }

  /** Frame the work from the standing three-quarter view a maker holds a part at.
   *
   * Not by its bounding sphere: three hinge leaves in a row are a long thin box, and a
   * sphere round them is mostly air, so the part ends up a smudge in the middle of an empty
   * pane. The box is measured along the camera's own right and up instead, against the
   * pane's real aspect, so a wide scene fills a wide pane.
   */
  function fit(): void {
    container.dataset["framed"] = "";
    aimed(bounds, STANDING);
  }

  /** Stand looking at `box` from `from` - a unit direction out of it - near enough that it
   * fills the pane, as `fit` frames the whole scene and `framePlace` one place of it. */
  function aimed(box: THREE.Box3, from: THREE.Vector3): void {
    fitting = true;
    try {
      aim(box, from.clone());
    } finally {
      fitting = false;
    }
  }

  function aim(box: THREE.Box3, from: THREE.Vector3): void {
    const centre = box.getCenter(new THREE.Vector3());
    const half = box.getSize(new THREE.Vector3()).multiplyScalar(0.5);
    const rect = container.getBoundingClientRect();
    const aspect = Math.max(rect.width, 1) / Math.max(rect.height, 1);

    const forward = from.clone().negate();
    const right = new THREE.Vector3().crossVectors(forward, camera.up).normalize();
    const up = new THREE.Vector3().crossVectors(right, forward).normalize();
    // How far the box reaches along one direction: the support function of a box, which is
    // the only thing about a box that a rotation does not complicate.
    const reach = (axis: THREE.Vector3): number =>
      Math.abs(axis.x) * half.x + Math.abs(axis.y) * half.y + Math.abs(axis.z) * half.z;

    const tan = Math.tan((FOV * Math.PI) / 360);
    const away =
      (Math.max(reach(right) / (tan * aspect), reach(up) / tan) + reach(forward)) * 1.08 + 1;
    camera.position.copy(centre).add(from.multiplyScalar(away));
    camera.near = Math.max(away / 800, NEAR);
    camera.far = away * 10;
    controls.target.copy(centre);
    controls.update();
    camera.updateProjectionMatrix();
    draw();
  }

  /** Where to stand to see `ref`, with the body it is a place of - or `null` when no drawn
   * body carries a sight for it. */
  function sightOf(ref: string): { readonly sight: SightView; readonly body: Body } | null {
    for (const body of bodies) {
      const sight = body.part.sights[ref];
      if (sight !== undefined) return { sight, body };
    }
    return null;
  }

  /** Turn to one place, from where Python said to stand - see `Viewer3D.frame`. *On bed* the
   * box and the way out of it are moved by the body's own placement, the matrix the body is
   * already drawn with, rather than anything worked out here. A place smaller than a little of
   * the scene is framed with some of what is round it, so a 2 mm face is not a camera pressed
   * against it with nothing to say where it is. */
  function framePlace(ref: string): void {
    const found = sightOf(ref);
    if (found === null) return;
    const laid = look === "bed" ? found.body.placement : null;
    if (look === "bed" && laid === null) return;
    const [x0, y0, z0, x1, y1, z1] = found.sight.bounds;
    const box = new THREE.Box3(new THREE.Vector3(x0, y0, z0), new THREE.Vector3(x1, y1, z1));
    const eye = new THREE.Vector3(...found.sight.eye);
    if (laid !== null) {
      box.applyMatrix4(laid);
      eye.transformDirection(laid);
    }
    const least = Math.max(bounds.getSize(new THREE.Vector3()).length() * PLACE_LEAST, 10);
    const size = box.getSize(new THREE.Vector3()).max(new THREE.Vector3(least, least, least));
    box.setFromCenterAndSize(box.getCenter(new THREE.Vector3()), size);
    aimed(box, eye);
    touched = true;
    container.dataset["framed"] = ref;
  }

  // ---- picking ---------------------------------------------------------------

  const caster = new THREE.Raycaster();
  caster.params.Line = { threshold: LINE_PICK };
  const where = new THREE.Vector2();

  /** What one hit of the ray answers to, or `null` when it is nothing of ours. A triangle, a
   * segment or a line of lettering with no name of its own answers to its part.
   *
   * Never `hit.faceIndex`/`hit.index` alone: those count a position in whatever three.js just
   * walked, and hiding gives a body's geometry an index that leaves triangles out, so that
   * position is not the same number as the triangle's own once anything is hidden. `face.a` -
   * a triangle's first *vertex* - is not: `bodyOf` lays three unshared vertices per triangle
   * straight into `positions`, in order, so `face.a / 3` is the triangle's own number whether
   * the geometry is indexed or not, the same way `index.getX(hit.index)` is a line segment's
   * first vertex regardless of which entries of the index were kept. */
  function foundBy(hit: THREE.Intersection): Found | null {
    const triangle = hit.face !== null && hit.face !== undefined ? Math.floor(hit.face.a / 3) : -1;
    const body = bodies.find((one) => one.mesh === hit.object);
    if (body !== undefined) {
      const ref = refIn(body.refs, body.index, triangle) ?? body.part.ref;
      return { ref, part: body.part, context: null };
    }
    const lines = scored.find((one) => one.lines === hit.object);
    if (lines !== undefined) {
      const at = hit.index ?? -2;
      const vertex = lines.lines.geometry.index?.getX(at) ?? at;
      const segment = Math.floor(vertex / 2);
      const ref = refIn(lines.refs, lines.index, segment) ?? lines.part.ref;
      return { ref, part: lines.part, context: null };
    }
    const words = lettered.find((one) => one.quad === hit.object);
    if (words !== undefined) return { ref: words.ref ?? words.part.ref, part: words.part, context: null };
    // A context body answers only by a face's own name - never its label for a triangle of
    // none, since an imported body is nothing but those and must not be a thing to click.
    const ghost = ghosts.find((one) => one.mesh === hit.object);
    if (ghost !== undefined) {
      const ref = refIn(ghost.refs, ghost.index, triangle);
      return ref === null ? null : { ref, part: null, context: ghost.context };
    }
    return null;
  }

  /** What is under the pointer, or `null`. */
  function under(event: PointerEvent): Found | null {
    const rect = view.domElement.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    where.set(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    caster.setFromCamera(where, camera);
    // A context body is drawn round and over the work, so a part anywhere along the ray wins
    // and a ghost's face is only the answer when no part is under the pointer at all.
    let behind: Found | null = null;
    for (const hit of caster.intersectObjects(parts.children, false)) {
      // Nor does it know what is drawn: *On bed* hides a cut part and every context body, and
      // what is not drawn is not under the pointer.
      if (!hit.object.visible) continue;
      // The raycaster knows nothing of clipping planes - it would happily hand back a
      // triangle the section has clipped away, since that clip only ever happened in the
      // fragment shader. So a section on filters the same way it paints: a hit on the wrong
      // side of the plane is not under the pointer at all.
      if (view.localClippingEnabled && clipPlane.distanceToPoint(hit.point) < 0) continue;
      const found = foundBy(hit);
      if (found === null) continue;
      // Belt and braces beside `applyHidden`'s own index rebuild, which is what actually
      // keeps a hidden triangle out of the raycast: `quad.visible = false` on a line of
      // lettering does not stop a raycast meeting it (three.js's own raycaster reads no
      // object's `visible`), so a hidden ref is refused here too, on every kind of hit alike -
      // and a hit refused here is a hit skipped, which is what lets a click through to
      // whatever undrawn geometry sits behind it.
      if (isHidden(found.ref)) continue;
      if (found.part === null) {
        behind ??= found;
        continue;
      }
      return found;
    }
    return behind;
  }

  let pressed: { x: number; y: number } | null = null;

  view.domElement.addEventListener("pointerdown", (event: PointerEvent) => {
    if (event.button !== 0) return;
    pressed = { x: event.clientX, y: event.clientY };
  });

  view.domElement.addEventListener("pointerup", (event: PointerEvent) => {
    const from = pressed;
    pressed = null;
    if (from === null || event.button !== 0) return;
    if (Math.abs(event.clientX - from.x) + Math.abs(event.clientY - from.y) > CLICK_SLOP) return;
    const found = under(event);
    // A part always wins a click, detection on or not; the backdrop only gets a turn once
    // nothing in front of it answered, which is what keeps detecting faces from changing
    // what an ordinary click on the work does.
    if (found === null && detectedIndex !== null) {
      hooks.onDetectPick(detectedAt(event));
      return;
    }
    // A context body is never half of a fit - it is not a part - so a shift-click onto one,
    // or from one, is an ordinary pick.
    if (event.shiftKey && found !== null && found.part !== null && chosen !== null) {
      // task-61's second pick: only counts when it lands on a part other than the first
      // pick's - a shift-click on the same part, or with nothing picked yet, changes
      // nothing, so a maker cannot lose the first pick by shift-clicking somewhere that
      // does not qualify as a second face.
      const firstPart = partRefOf(chosen);
      if (firstPart !== null && found.part.ref !== firstPart) {
        chosenSecond = found.ref;
        paint();
        hooks.onSelectSecond(found.ref);
        return;
      }
    }
    const ref = found?.ref ?? null;
    chosen = ref;
    chosenSecond = null;
    paint();
    hooks.onSelect(ref);
  });

  // A press the browser takes away - a scroll, a system gesture - is not a click waiting to
  // land, and must not become one when a later pointer comes up nearby.
  view.domElement.addEventListener("pointercancel", () => {
    pressed = null;
  });

  view.domElement.addEventListener("pointermove", (event: PointerEvent) => {
    if (pressed !== null) return; // orbiting, not looking
    const found = under(event);
    const ref = found?.ref ?? null;
    if (ref !== hovered) {
      hovered = ref;
      paint();
    }
    tip.hidden = found === null;
    if (found !== null) {
      tipRef.textContent = found.ref;
      tipPart.textContent =
        found.part === null ? "context · not a part, not exported" : caption(found.part, sheetsOf);
      const rect = container.getBoundingClientRect();
      tip.style.left = `${Math.round(event.clientX - rect.left + 12)}px`;
      tip.style.top = `${Math.round(event.clientY - rect.top + 14)}px`;
    }
    view.domElement.style.cursor = found === null ? "grab" : "pointer";
  });

  view.domElement.addEventListener("pointerleave", () => {
    pressed = null;
    if (hovered === null) return;
    hovered = null;
    tip.hidden = true;
    paint();
  });

  const watcher = new ResizeObserver(() => {
    if (!touched) fit();
    else draw();
  });
  watcher.observe(container);

  return {
    show,
    fit() {
      touched = false;
      fit();
    },
    frame: framePlace,
    zoom(factor) {
      const to = controls.target;
      camera.position.sub(to).multiplyScalar(1 / factor).add(to);
      touched = true;
      controls.update();
      draw();
    },
    select(ref) {
      chosen = ref;
      chosenSecond = null;
      paint();
    },
    selectSecond(ref) {
      chosenSecond = ref;
      paint();
    },
    point(ref) {
      pointed = ref;
      paint();
    },
    selected: () => chosen,
    selectedSecond: () => chosenSecond,
    empty: () => bodies.length === 0,
    say(text) {
      note.textContent = text;
    },
    detect,
    mode: applyMode,
    section: applySection,
    colourFaces(on) {
      colouring = on;
      paint();
    },
    markReference,
    hide(refs) {
      hiddenRefs = refs;
      applyHidden();
    },
  };
}
