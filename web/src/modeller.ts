/** The solid modeller, as calls and nothing else: numbers and handles in, handles and buffers
 * out.
 *
 * Every decision about a body is Python's. `bench.adapters.browser` walks the tree, works out
 * which named face each triangle of a fresh primitive lies on (`bench.meshing`), builds the
 * transforms, and reads the names back off the result. This module holds the one thing Python
 * in the worker cannot: Manifold's WASM objects. It keeps each one in a table under an integer
 * handle, forwards the call it was asked for, and frees the lot on `release()` - so there is no
 * geometry here, no matrix arithmetic, and no recipe to parse.
 *
 * **What crosses, and how.** Bulk numbers cross as buffers, never as JSON: Python passes an
 * `array.array`, which arrives as a proxy whose `getBuffer` is a view straight onto Python's
 * memory, and a mesh goes back as the typed arrays Manifold made, which Python reads with
 * `.to_py()`. Everything else is a handle, a count or a single number. A call a table cannot
 * answer - a handle freed or never made - throws, and the adapter turns that into the error
 * scene a refused body has always been.
 *
 * **One grid for every vertex.** A body that has been through a `Mesh` - every primitive, which
 * `tagged` rebuilds to mark its faces, and every imported sweep - holds its vertices as 32-bit
 * floats, because that is what a `Mesh` carries. A transform works in doubles, so before
 * task-77 a moved body landed off that grid while a hull or a sweep built on the same numbers
 * sat on it, and two faces drawn to meet came out up to half a float's last place apart: a
 * loft's top rounded to z = 70.0840835571289 under a cylinder moved to 70.08408650799234, and
 * the union kept the 3 micrometre gap between them - two bodies, and the face between them read
 * as a 90 degree ceiling. So `transform` puts what it moved back on the grid (`onTheGrid`): the
 * same number drawn two ways rounds to the same float, and a union meets itself.
 *
 * **One trap, kept out of here.** Manifold's `transform` takes a column-major 4 by 4. The
 * sixteen numbers arrive already in that order, from `bench.meshing.column_major`, so this
 * module never reorders a matrix.
 */
import type { CrossSection, Manifold, ManifoldToplevel, Mat4, Vec2, Vec3 } from "manifold-3d";

/** A Python buffer as Pyodide hands it over: a view onto Python's own memory, released once
 * read. */
interface PyBuffer {
  getBuffer(type: "f64" | "u32"): { readonly data: ArrayLike<number>; release(): void };
}

/** Numbers from Python - or, for a caller in JavaScript, any list of them. */
export type Numbers = PyBuffer | ArrayLike<number>;

/** A body's boundary exactly as Manifold made it. `vertices` holds `num_prop` numbers per
 * vertex, the first three of which are its position. */
export interface MeshBuffers {
  readonly num_prop: number;
  readonly vertices: Float32Array;
  readonly triangles: Uint32Array;
  readonly run_index: Uint32Array;
  readonly run_original_id: Uint32Array;
  readonly face_id: Uint32Array;
}

/** A body rebuilt with a face id on every triangle, and the original id that marks it. */
export interface Tagged {
  readonly body: number;
  readonly mark: number;
}

/** What `bench.adapters.browser.Modeller` calls. Snake case, because Python is the caller. */
export interface Modeller {
  section(rings: Numbers, lengths: Numbers): number;
  /** `twist` is in degrees, counter-clockwise about +Z, reached at the top over `divisions`
   * extra copies of the section; `scale` is the top's size beside the bottom's. Left out,
   * they are the plain prism. */
  extrude(section: number, height: number, divisions?: number, twist?: number, scale?: number): number;
  revolve(section: number, segments: number, degrees: number): number;
  transform(body: number, columns: Numbers): number;
  union(a: number, b: number): number;
  difference(a: number, b: number): number;
  intersection(a: number, b: number): number;
  hull(points: Numbers): number;
  imported(vertices: Numbers, triangles: Numbers): number;
  tagged(body: number, faces: Numbers): Tagged;
  mesh(body: number): MeshBuffers;
  num_tri(body: number): number;
  is_empty(body: number): boolean;
  volume(body: number): number;
  min_gap(a: number, b: number, upto: number): number;
  /** Free every object made since the last release. */
  release(): void;
}

/** Load Manifold's WASM from `base`, which is a directory this app serves itself.
 *
 * The module is imported by URL rather than by name so the bundler leaves it alone and the
 * `.wasm` beside it is the copy under `public/`, exactly as Pyodide's is. Nothing is fetched
 * from a CDN.
 */
export async function load(base: string): Promise<ManifoldToplevel> {
  const module: { default: (config?: { locateFile: () => string }) => Promise<ManifoldToplevel> } =
    await import(/* @vite-ignore */ new URL("manifold.js", base).href);
  const wasm = await module.default({ locateFile: () => new URL("manifold.wasm", base).href });
  wasm.setup();
  return wasm;
}

/** `moved` with every vertex rounded to the nearest 32-bit float - the grid every body read in
 * through a `Mesh` already stands on. `warpBatch` only moves vertices, so the triangles and the
 * face ids they carry are untouched. Rounding the positions of what is already the answer is not
 * geometry: nothing is decided here, only kept on the one grid Python's numbers all land on. */
function onTheGrid(moved: Manifold): Manifold {
  const rounded = moved.warpBatch((verts) => {
    for (let at = 0; at < verts.length; at += 1) verts[at] = Math.fround(verts[at] ?? 0);
  });
  moved.delete();
  return rounded;
}

type Held = { readonly kind: "section"; readonly one: CrossSection } | { readonly kind: "body"; readonly one: Manifold };

const isPyBuffer = (given: Numbers): given is PyBuffer =>
  typeof (given as Partial<PyBuffer>).getBuffer === "function";

/** `use` handed the numbers `given` holds, released afterwards when they are Python's. */
function reading<T>(given: Numbers, type: "f64" | "u32", use: (data: ArrayLike<number>) => T): T {
  if (!isPyBuffer(given)) return use(given);
  const buffer = given.getBuffer(type);
  try {
    return use(buffer.data);
  } finally {
    buffer.release();
  }
}

/** The object handed to Python as the run's modeller. */
export function bind(wasm: ManifoldToplevel): Modeller {
  const table = new Map<number, Held>();
  let next = 1;

  const keep = (held: Held): number => {
    const handle = next;
    next += 1;
    table.set(handle, held);
    return handle;
  };
  const body = (handle: number): Manifold => {
    const held = table.get(handle);
    if (held?.kind !== "body") throw new Error(`there is no body ${handle}`);
    return held.one;
  };
  const section = (handle: number): CrossSection => {
    const held = table.get(handle);
    if (held?.kind !== "section") throw new Error(`there is no cross-section ${handle}`);
    return held.one;
  };
  const made = (one: Manifold): number => keep({ kind: "body", one });

  return {
    section: (rings, lengths) =>
      reading(rings, "f64", (flat) =>
        reading(lengths, "u32", (counts) => {
          const polygons: Vec2[][] = [];
          let at = 0;
          for (let ring = 0; ring < counts.length; ring += 1) {
            const polygon: Vec2[] = [];
            for (let point = 0; point < (counts[ring] ?? 0); point += 1) {
              polygon.push([flat[at] ?? 0, flat[at + 1] ?? 0]);
              at += 2;
            }
            polygons.push(polygon);
          }
          return keep({ kind: "section", one: new wasm.CrossSection(polygons, "EvenOdd") });
        }),
      ),
    // The plain call is left exactly as it always was. Manifold's binding reads a bare number
    // for the top scale as a vector with its Y missing - measured: a unit scale came back as a
    // wedge of half the volume - so the scale crosses as the pair it really takes.
    extrude: (handle, height, divisions, twist, scale) =>
      made(
        divisions === undefined && twist === undefined && scale === undefined
          ? section(handle).extrude(height)
          : section(handle).extrude(height, divisions ?? 0, twist ?? 0, [scale ?? 1, scale ?? 1]),
      ),
    revolve: (handle, segments, degrees) => made(section(handle).revolve(segments, degrees)),
    transform: (handle, columns) =>
      reading(columns, "f64", (matrix) => made(onTheGrid(body(handle).transform(Array.from(matrix) as Mat4)))),
    union: (a, b) => made(body(a).add(body(b))),
    difference: (a, b) => made(body(a).subtract(body(b))),
    intersection: (a, b) => made(body(a).intersect(body(b))),
    hull: (points) =>
      reading(points, "f64", (flat) => {
        const cloud: Vec3[] = [];
        for (let at = 0; at + 2 < flat.length; at += 3) {
          cloud.push([flat[at] ?? 0, flat[at + 1] ?? 0, flat[at + 2] ?? 0]);
        }
        return made(wasm.Manifold.hull(cloud));
      }),
    imported: (vertices, triangles) =>
      reading(vertices, "f64", (points) =>
        reading(triangles, "u32", (corners) =>
          // Manifold's own constructor is the whole of the validation, and there is no check
          // here beside it: it throws when what it was handed is not an oriented 2-manifold,
          // and the adapter turns that into the same refusal every other bad call already
          // becomes. Measured against this Manifold rather than assumed - an open boundary,
          // a non-finite vertex and an index past the end each throw by name, so a `status()`
          // check after it would be a branch nothing reaches.
          made(
            new wasm.Manifold(
              new wasm.Mesh({
                numProp: 3,
                vertProperties: Float32Array.from(points),
                triVerts: Uint32Array.from(corners),
              }),
            ),
          ),
        ),
      ),
    tagged: (handle, faces) => {
      // A mesh's face ids can only be set on the way in, so the body is meshed, given one
      // reserved original id and the face ids it was sent, and rebuilt. A body with no
      // triangles has nothing to mark and no mesh Manifold would take back, so it comes
      // through as it is with a mark nothing will ever match.
      const one = body(handle);
      const mark = wasm.Manifold.reserveIDs(1);
      if (one.isEmpty()) return { body: handle, mark };
      const mesh = one.getMesh();
      const rebuilt = new wasm.Mesh({
        numProp: mesh.numProp,
        vertProperties: new Float32Array(mesh.vertProperties),
        triVerts: new Uint32Array(mesh.triVerts),
        runIndex: new Uint32Array([0, mesh.triVerts.length]),
        runOriginalID: new Uint32Array([mark]),
        faceID: reading(faces, "u32", (ids) => Uint32Array.from(ids)),
      });
      return { body: made(new wasm.Manifold(rebuilt)), mark };
    },
    mesh: (handle) => {
      const mesh = body(handle).getMesh();
      return {
        num_prop: mesh.numProp,
        vertices: mesh.vertProperties,
        triangles: mesh.triVerts,
        run_index: mesh.runIndex,
        run_original_id: mesh.runOriginalID,
        face_id: mesh.faceID,
      };
    },
    num_tri: (handle) => body(handle).numTri(),
    is_empty: (handle) => body(handle).isEmpty(),
    volume: (handle) => body(handle).volume(),
    min_gap: (a, b, upto) => body(a).minGap(body(b), upto),
    release: () => {
      for (const held of table.values()) {
        try {
          held.one.delete();
        } catch {
          // already freed by Manifold itself, which is not a reason to keep the rest
        }
      }
      table.clear();
    },
  };
}
