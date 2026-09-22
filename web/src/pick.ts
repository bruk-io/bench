/** A pick, resolved to the numbers a `[reference]` table holds - decision-7, in one place with
 * no DOM in it.
 *
 * The view answers a click with a point in the dropped body's own coordinates (`viewer3d.ts`'s
 * `DetectHit`) and the worker answers a detection with the three points that body's own
 * `origin` words name and the distance within which a point *is* one of them
 * (`bench.worker.detected`). Everything here is arithmetic over those two: how far a picked
 * point is from each named point, which word it resolves to, and how a field's text reads as
 * the word or the triple `bench.placement.placement` will read back.
 *
 * Every number comes from Python. Nothing here measures geometry of its own: no transform, no
 * normal, no area - only distances between points somebody else computed, which is what
 * deciding "is this the corner the report calls `low`" costs.
 *
 * **The snap is not a tolerance on a mouse.** `bench.survey.ROUND` is a hundredth of a
 * millimetre, which at any framing a person orbits at is a small fraction of one pixel: no
 * click lands inside it, and a rule that waited for one would never fire. So the maker's own
 * choice decides between the word and the triple - they assign the hit, or the corner nearest
 * it - and `ROUND` only certifies that what they chose *is* the named point, which on a body
 * whose corner is a vertex it exactly is, to the last float the exporter wrote. No figure is
 * invented here for how near a click has to be (decision-5), because no click has to be near
 * anything: it has to be *on* something, and a vertex is something.
 */
import type { ReferenceValue, Triple } from "./values";

/** A point in the dropped body's own coordinates. */
export type Point3 = readonly [number, number, number];

/** One of the points a `[reference]` `origin` word names, as `bench.worker.detected` reports
 * it: the word, and where it is in the body's own coordinates. */
export interface NamedOrigin {
  readonly name: string;
  readonly point: Point3;
}

/** A named point and how far a picked point is from it, in millimetres. */
export interface Away {
  readonly name: string;
  readonly away: number;
}

/** Millimetres between two points. */
export const between = (a: Point3, b: Point3): number =>
  Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

/** How far `point` is from each named point, in the order they were given - the readout's own
 * line, so a maker can see that the corner they are about to assign is the one the report
 * calls `low` rather than being told so. */
export const distances = (point: Point3, origins: readonly NamedOrigin[]): readonly Away[] =>
  origins.map((one) => ({ name: one.name, away: between(point, one.point) }));

/** The named point nearest `point`, or `null` when there are none to be near. */
export function nearest(point: Point3, origins: readonly NamedOrigin[]): Away | null {
  let found: Away | null = null;
  for (const one of distances(point, origins)) {
    if (found === null || one.away < found.away) found = one;
  }
  return found;
}

/** `point` as a `[reference]` table's `origin`: the word, when it is within `round` of the
 * point that word names, and otherwise the triple it measured.
 *
 * The triple is not a fallback for a failure - on any body that is not an axis-aligned box it
 * is the answer, which is most of them (decision-7). `round` is `bench.survey.ROUND` as the
 * detection reported it, never a figure this module holds. */
export function resolvedOrigin(
  point: Point3,
  origins: readonly NamedOrigin[],
  round: number,
): ReferenceValue {
  const near = nearest(point, origins);
  if (near !== null && near.away <= round) return near.name;
  return [point[0], point[1], point[2]] as Triple;
}

/** A vector as a `[reference]` table's `up`: the triple it measured, always.
 *
 * A normal that is nearly `+Z` is *not* written as `"+Z"`: that would need a tolerance on an
 * angle, and decision-7 says plainly that nothing stands in for one yet - none of the survey's
 * own tolerances is an angle. A maker who wants the word types it, in the field this fills. */
export const resolvedUp = (normal: Point3): Triple => [normal[0], normal[1], normal[2]];

/** A `[reference]` value as the field holding it reads: a word as itself, a triple as the
 * three numbers, full precision, since this text is what a commit writes down. */
export const fieldText = (value: ReferenceValue): string =>
  typeof value === "object" ? value.join(", ") : String(value);

/** What a maker typed (or a pick filled in) as the value it is: three numbers as a triple,
 * anything else as the word it is, and nothing at all as `null`.
 *
 * What the word *means* is not checked here, exactly as `values.ts` does not check it:
 * `bench.placement.placement` refuses `"lo"` or a `+W` axis by name when the run reads the
 * table, which is the one reader that should be saying so. */
export function fieldValue(text: string): ReferenceValue | null {
  const said = text.trim();
  if (said === "") return null;
  const parts = said.split(",").map((one) => one.trim());
  if (parts.length === 3) {
    // `Number("")` is 0, so an empty part is refused by itself: `", ,"` is not the origin.
    if (parts.every((one) => one !== "" && Number.isFinite(Number(one)))) {
      const [x, y, z] = parts.map(Number) as [number, number, number];
      return [x, y, z] as Triple;
    }
    return null; // three of something that is not three numbers is not a word either
  }
  return said;
}

/** A point as a readout shows it - rounded for the eye only. Never what is written down: a
 * tenth of `ROUND` of display rounding would push a point that *is* `Extent.low` out of the
 * snap it should pass. */
export const shown = (point: Point3, digits = 3): string =>
  `(${point.map((one) => one.toFixed(digits)).join(", ")})`;

/** Millimetres as the readout says them. */
export const mm = (span: number, digits = 3): string => `${span.toFixed(digits)} mm`;
