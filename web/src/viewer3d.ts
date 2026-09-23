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
 * told its own up vector and the orbit follows. Nothing rotates the geometry: a part in the
 * viewer lies the way it lies on the bed, and the grid it lies on is the XY plane.
 *
 * **For a test to read.** A canvas is one opaque element, so what is on it is also said on
 * the container: `data-bodies` and `data-triangles` for what was drawn, `data-bounds` for the
 * box it fills, `data-selected` and `data-pointed` for the refs lit, `data-lit` for how many
 * triangles are painted as selected, `data-distance` for how far the camera stands from what
 * it looks at, and `data-datum` for how long the origin's own X/Y/Z arms are drawn.
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import type {
  FrameView,
  GridView,
  LetteringView,
  MarksView,
  MeshView,
  PartView,
  SheetView,
  StageView,
} from "./scene";

const FOV = 35;
const NEAR = 0.05;
const FAR = 20_000;
const CLICK_SLOP = 4; // px of pointer travel that is still a click, not a drag
const LINE_PICK = 0.8; // mm either side of an engraved line that still picks it
const LETTER_PX = 64; // the height lettering is rendered at before it is laid on its box

/** The four states a face can be in, and the ink an engraving is drawn in when it is in none
 * of them. */
const BASE = new THREE.Color(0x9fb0c0);
const INK = new THREE.Color(0x2f353b);
const HOVER = new THREE.Color(0xc8d6e2);
const SELECTED = new THREE.Color(0x00aaaa);
const CURSOR = new THREE.Color(0xe38b00);

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
   * where the stage says. `sheets` is only read to say which sheet a part is cut from, and
   * `reference` is a body somebody else made, stood behind the work and never selectable. */
  show(
    parts: readonly PartView[],
    stage: StageView,
    sheets: readonly SheetView[],
    reference?: MeshView | null,
  ): void;
  /** Frame everything, and forget that anybody moved the camera. */
  fit(): void;
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
  /** Light the dropped body up, or put it back to its plain ghost.
   *
   * The backdrop is still never *clickable* outside detection - it answers no raycast, so a
   * click on the work behind it is a click on the work. This is the other direction only: the
   * refs container can say "this one", and the view shows which. While `detect` is on the
   * backdrop is wearing its flats' colours and this does nothing, since being told which body
   * is meant is not a reason to throw away the measurement being looked at. */
  markReference(lit: boolean): void;
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

/** What is under the pointer: the ref it answers to, and the part it belongs to. */
interface Found {
  readonly ref: string;
  readonly part: PartView;
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
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch {
    // No WebGL at all - an old browser, a blocked context, a machine with no GPU driver.
    // Everything else still works, so say so here and let the rest of the app carry on.
  }

  if (renderer === null) {
    note.textContent = "this browser has no WebGL, so the parts cannot be drawn; the cut files still export";
    return {
      show: () => {},
      fit: () => {},
      zoom: () => {},
      select: () => {},
      selectSecond: () => {},
      point: () => {},
      selected: () => null,
      selectedSecond: () => null,
      empty: () => true,
      say: () => {},
      detect: () => {},
      markReference: () => {},
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

  const grid = new THREE.GridHelper(1, 1, 0x9aa0a6, 0xcfd4da);
  grid.rotateX(Math.PI / 2);
  const lines = grid.material;
  if (lines instanceof THREE.Material) {
    lines.transparent = true;
    lines.opacity = 0.55;
  }
  scene.add(grid);

  const parts = new THREE.Group();
  scene.add(parts);

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

  /** `ref`'s frame, read off whichever body's `PartView.frames` names it, or `null` for a
   * ref with none - unpicked, no body drawn for it, or a face `plane_of` could not frame. */
  function frameOf(ref: string | null): FrameView | null {
    if (ref === null) return null;
    for (const body of bodies) {
      const found = body.part.frames[ref];
      if (found !== undefined) return found;
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
      if (found === null) continue;
      faceFrames.add(frameGizmo(found, length));
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

  /** Draw once, on the next frame; several changes in one tick cost one picture. */
  function draw(): void {
    container.dataset["distance"] = camera.position.distanceTo(controls.target).toFixed(1);
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

  /** Put every colour back from what is selected, pointed at and hovered. */
  function paint(): void {
    let lit = 0;
    for (const body of bodies) {
      for (let triangle = 0; triangle < body.index.length; triangle += 1) {
        const colour = shade(refIn(body.refs, body.index, triangle) ?? body.part.ref, BASE);
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
    container.dataset["selected"] = chosen ?? "";
    container.dataset["second"] = chosenSecond ?? "";
    container.dataset["pointed"] = pointed ?? "";
    container.dataset["lit"] = String(lit);
    layFaceFrames();
    draw();
  }

  function clear(): void {
    for (const body of bodies) {
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
    if (standing !== null) {
      standing.geometry.dispose();
      const material = standing.material;
      if (material instanceof THREE.Material) material.dispose();
      standing = null;
    }
    detectedIndex = null;
    backdrop.clear();
    parts.clear();
    bodies = [];
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
      }),
    );
    backdrop.add(standing);
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
    });
    const mesh = new THREE.Mesh(geometry, surface);
    parts.add(mesh);
    return { mesh, refs, index, colors, part };
  }

  function scoredOf(part: PartView, marks: MarksView): Scored {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(marks.segments, 3));
    const colors = new THREE.BufferAttribute(new Float32Array(marks.segments.length), 3);
    geometry.setAttribute("color", colors);
    const drawn = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ vertexColors: true }));
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
  ): void {
    clear();
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

    const [x0 = -50, y0 = -50, z0 = 0, x1 = 50, y1 = 50, z1 = 50] = stage.bounds;
    bounds = new THREE.Box3(new THREE.Vector3(x0, y0, z0), new THREE.Vector3(x1, y1, z1));
    // The stage measures the work, and a dropped body is not part of it - but if somebody
    // dropped it they meant to look at it, and a backdrop framed out of view or drawn as a
    // speck in the corner is the same as one that never arrived. So the view is framed round
    // both, at the cost of the work reading smaller beside a large reference.
    if (standing !== null) {
      standing.geometry.computeBoundingBox();
      const around = standing.geometry.boundingBox;
      if (around !== null) bounds.union(around);
    }
    // Origin included too, always - the datum's whole point is showing where it sits relative
    // to the work, which a box that only ever covered the work could not do the one time that
    // question matters: everything sits hundreds of millimetres from a dropped body's origin.
    bounds.expandByPoint(ORIGIN);
    layDatum(bounds);
    container.dataset["bodies"] = String(bodies.length);
    container.dataset["triangles"] = String(bodies.reduce((sum, one) => sum + one.index.length, 0));
    container.dataset["bounds"] = stage.bounds.join(",");
    lay(stage.grid);

    // A selected or pointed-at ref the new scene no longer has is dropped, and the host is
    // told, so the status bar does not keep offering a name nothing answers to.
    const lost = chosen !== null && !known(chosen);
    if (lost) chosen = null;
    const lostSecond = chosenSecond !== null && !known(chosenSecond);
    if (lostSecond) chosenSecond = null;
    if (pointed !== null && !known(pointed)) pointed = null;
    hovered = null;
    paint();
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
    if (arrived || (!touched && (bodies.length > 0 || standing !== null))) fit();
    else draw();
  }

  const known = (ref: string): boolean =>
    bodies.some((one) => one.part.ref === ref || one.refs.includes(ref)) ||
    scored.some((one) => one.refs.includes(ref)) ||
    lettered.some((one) => one.ref === ref);

  /** The floor the stage asked for. */
  function lay(floor: GridView): void {
    const old = grid.geometry;
    grid.geometry = new THREE.GridHelper(floor.size, floor.divisions).geometry;
    old.dispose();
    const [x = 0, y = 0] = floor.centre;
    grid.position.set(x, y, 0);
  }

  /** Frame the work from the standing three-quarter view a maker holds a part at.
   *
   * Not by its bounding sphere: three hinge leaves in a row are a long thin box, and a
   * sphere round them is mostly air, so the part ends up a smudge in the middle of an empty
   * pane. The box is measured along the camera's own right and up instead, against the
   * pane's real aspect, so a wide scene fills a wide pane.
   */
  function fit(): void {
    fitting = true;
    try {
      frame_();
    } finally {
      fitting = false;
    }
  }

  function frame_(): void {
    const centre = bounds.getCenter(new THREE.Vector3());
    const half = bounds.getSize(new THREE.Vector3()).multiplyScalar(0.5);
    const rect = container.getBoundingClientRect();
    const aspect = Math.max(rect.width, 1) / Math.max(rect.height, 1);

    const from = new THREE.Vector3(0.78, -1, 0.6).normalize();
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

  // ---- picking ---------------------------------------------------------------

  const caster = new THREE.Raycaster();
  caster.params.Line = { threshold: LINE_PICK };
  const where = new THREE.Vector2();

  /** What one hit of the ray answers to, or `null` when it is nothing of ours. A triangle, a
   * segment or a line of lettering with no name of its own answers to its part. */
  function foundBy(hit: THREE.Intersection): Found | null {
    const body = bodies.find((one) => one.mesh === hit.object);
    if (body !== undefined) {
      const triangle = hit.faceIndex ?? -1;
      return { ref: refIn(body.refs, body.index, triangle) ?? body.part.ref, part: body.part };
    }
    const lines = scored.find((one) => one.lines === hit.object);
    if (lines !== undefined) {
      const segment = Math.floor((hit.index ?? -2) / 2);
      return { ref: refIn(lines.refs, lines.index, segment) ?? lines.part.ref, part: lines.part };
    }
    const words = lettered.find((one) => one.quad === hit.object);
    if (words !== undefined) return { ref: words.ref ?? words.part.ref, part: words.part };
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
    for (const hit of caster.intersectObjects(parts.children, false)) {
      const found = foundBy(hit);
      if (found !== null) return found;
    }
    return null;
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
    if (event.shiftKey && found !== null && chosen !== null) {
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
      tipPart.textContent = caption(found.part, sheetsOf);
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
    markReference,
  };
}
