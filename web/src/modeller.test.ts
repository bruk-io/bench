import type { ManifoldToplevel } from "manifold-3d";
import { beforeAll, describe, expect, it } from "vitest";

import { type Modeller, bind, load } from "./modeller";

let wasm: ManifoldToplevel;

beforeAll(async () => {
  // The copy under public/, served beside the page the way the app serves it.
  wasm = await load(new URL("/manifold/", window.location.href).href);
});

/** A 2 by 2 square, as the one ring Python would send. */
const SQUARE = { rings: [0, 0, 2, 0, 2, 2, 0, 2], lengths: [4] };

/** A unit cube as raw triangles, the way a dropped mesh arrives: eight corners, twelve
 * triangles, every one wound counter-clockwise seen from outside. */
const CUBE = {
  vertices: [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1],
  triangles: [
    0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0,
    4, 3, 4, 7,
  ],
};

const cube = (modeller: Modeller): number =>
  modeller.extrude(modeller.section(SQUARE.rings, SQUARE.lengths), 2);

const lowest = (modeller: Modeller, body: number): number => {
  const mesh = modeller.mesh(body);
  let low = Number.POSITIVE_INFINITY;
  for (let at = 0; at < mesh.vertices.length; at += mesh.num_prop) {
    low = Math.min(low, mesh.vertices[at + 2] ?? low);
  }
  return low;
};

describe("modeller, building", () => {
  it("sweeps a ring into a body of the volume it encloses", () => {
    const modeller = bind(wasm);
    expect(modeller.volume(cube(modeller))).toBeCloseTo(8, 6);
  });

  it("combines two bodies by handle", () => {
    const modeller = bind(wasm);
    const moved = modeller.transform(cube(modeller), [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1]);
    expect(modeller.volume(modeller.union(cube(modeller), moved))).toBeCloseTo(12, 6);
    expect(modeller.volume(modeller.intersection(cube(modeller), moved))).toBeCloseTo(4, 6);
    expect(modeller.volume(modeller.difference(cube(modeller), moved))).toBeCloseTo(4, 6);
  });

  it("reads a matrix as the column-major sixteen numbers it is sent", () => {
    const modeller = bind(wasm);
    const lifted = modeller.transform(cube(modeller), [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 5, 1]);
    expect(lowest(modeller, lifted)).toBeCloseTo(5, 5);
  });

  it("hulls a cloud of points", () => {
    const modeller = bind(wasm);
    const tetra = modeller.hull([0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]);
    expect(modeller.num_tri(tetra)).toBe(4);
    expect(modeller.volume(tetra)).toBeCloseTo(1 / 6, 6);
  });

  it("builds a body out of the triangles it is handed", () => {
    const modeller = bind(wasm);
    // A unit cube written out by hand, wound counter-clockwise seen from outside: the shape
    // a dropped mesh arrives in, with no section and no sweep anywhere near it.
    const body = modeller.imported(CUBE.vertices, CUBE.triangles);
    expect(modeller.num_tri(body)).toBe(12);
    expect(modeller.volume(body)).toBeCloseTo(1, 6);
  });

  it("refuses a mesh that bounds no body, which is the whole of the validation", () => {
    const modeller = bind(wasm);
    // One lone triangle: an open boundary. Manifold's own constructor is what says no, and
    // the throw is what the adapter turns into the error scene a refused body has always been.
    expect(() => modeller.imported([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 2])).toThrow();
  });

  it("measures the gap between two bodies, stopping at the distance asked", () => {
    const modeller = bind(wasm);
    const apart = modeller.transform(cube(modeller), [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 0, 0, 1]);
    expect(modeller.min_gap(cube(modeller), apart, 10)).toBeCloseTo(3, 5);
  });
});

describe("modeller, marking faces", () => {
  it("writes the face ids it is sent onto the body under one new original id", () => {
    const modeller = bind(wasm);
    const body = cube(modeller);
    const count = modeller.num_tri(body);
    const faces = Array.from({ length: count }, (_, at) => at % 3);
    const marked = modeller.tagged(body, faces);
    const mesh = modeller.mesh(marked.body);
    expect(Array.from(mesh.run_original_id)).toEqual([marked.mark]);
    expect(Array.from(mesh.face_id)).toEqual(faces);
  });

  it("gives every marking an original id of its own", () => {
    const modeller = bind(wasm);
    const one = modeller.tagged(cube(modeller), [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    const two = modeller.tagged(cube(modeller), [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    expect(one.mark).not.toBe(two.mark);
  });

  it("passes a body with no triangles through as it is", () => {
    const modeller = bind(wasm);
    const body = cube(modeller);
    const nothing = modeller.difference(body, body);
    expect(modeller.is_empty(nothing)).toBe(true);
    expect(modeller.tagged(nothing, []).body).toBe(nothing);
  });
});

describe("modeller, handles", () => {
  it("frees everything on release, after which a handle answers to nothing", () => {
    const modeller = bind(wasm);
    const body = cube(modeller);
    modeller.release();
    expect(() => modeller.volume(body)).toThrow("there is no body");
  });

  it("refuses a handle of the wrong kind", () => {
    const modeller = bind(wasm);
    const profile = modeller.section(SQUARE.rings, SQUARE.lengths);
    expect(() => modeller.volume(profile)).toThrow("there is no body");
    expect(() => modeller.extrude(cube(modeller), 1)).toThrow("there is no cross-section");
  });
});
