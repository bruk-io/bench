/** What the inspector is about, and what a scene says about each thing it can be about.
 *
 * decision-12: every thing has one home, and an action lives next to its subject. The subject is
 * whatever is selected - nothing (the project), a part, a face, or a reference mesh - and this
 * module turns a selection and a scene into that subject and into what the inspector lists under
 * it: a part's findings, its standing, the part and place the status bar's count jumps to, the
 * `mated(...)` line a pair of picked faces would write - and what stays selected when a run
 * replaces the scene, and the URL hash a selection is linked by (task-92).
 *
 * Pure: data in, data out. Nothing here counts triangles or measures anything - every number is
 * the scene's own, worked out in Python - it only sorts what a run reported by which part it is
 * about, which is a matter of ref paths.
 */
import type { PartView, ViolationView } from "./scene";

/** What the inspector shows. A ref that is a part's own is the part; any other ref is a face
 * (or an engraved line, or lettering - whatever a click on the view answers with). A reference
 * mesh is not a ref at all - nothing a run named - so it is a subject of its own kind. */
export type Subject =
  | { readonly kind: "project" }
  | { readonly kind: "part"; readonly ref: string }
  | { readonly kind: "face"; readonly ref: string }
  | { readonly kind: "reference"; readonly file: string };

export const PROJECT: Subject = { kind: "project" };

/** Whether `ref` is `inside` or names something inside it - `a` is within `a`, and `a/b` is
 * within `a`, but `ab` is not. The same "inside" the view paints by and the tree flags by. */
export const within = (ref: string, inside: string): boolean => ref === inside || ref.startsWith(`${inside}/`);

/** The part `ref` belongs to, or `null` when nothing in `parts` answers to it - the nearest one,
 * should one part's ref ever sit under another's. */
export function partOf(ref: string, parts: readonly PartView[]): PartView | null {
  let found: PartView | null = null;
  for (const part of parts) {
    if (within(ref, part.ref) && (found === null || part.ref.length > found.ref.length)) found = part;
  }
  return found;
}

/** The subject a selected ref makes: nothing selected is the project; a part's own ref is the
 * part; anything else a run named is a face. A ref no part answers to - a run that no longer
 * names it - is still a face: the view has already said whether it holds it. */
export function subjectOf(ref: string | null, parts: readonly PartView[]): Subject {
  if (ref === null) return PROJECT;
  return parts.some((part) => part.ref === ref) ? { kind: "part", ref } : { kind: "face", ref };
}

/** The part a subject is about, when it is about one - the part itself, or the part a face is
 * on. */
export function partRefOf(subject: Subject, parts: readonly PartView[]): string | null {
  if (subject.kind === "part") return subject.ref;
  if (subject.kind === "face") return partOf(subject.ref, parts)?.ref ?? null;
  return null;
}

/** What the checks found about `part`: every finding one of whose places is on it, in the
 * order the run reported them. A finding about two parts - a fit between them - is on both. */
export function findingsOn(part: string, violations: readonly ViolationView[]): ViolationView[] {
  return violations.filter((one) => one.refs.some((ref) => within(ref, part)));
}

/** The findings that name `ref` or something inside it - a face's own, for the face. */
export function findingsNaming(ref: string, violations: readonly ViolationView[]): ViolationView[] {
  return violations.filter((one) => one.refs.some((place) => within(place, ref)));
}

/** The findings that are on no part at all: a check with nothing to point at (a fit nothing
 * could measure), or places no part of this run answers to. They belong to the project. */
export function findingsOnNoPart(violations: readonly ViolationView[], parts: readonly PartView[]): ViolationView[] {
  return violations.filter((one) => !one.refs.some((ref) => partOf(ref, parts) !== null));
}

/** How a part stands, by the worst thing found on it: errors, then warnings, then only what
 * nothing could measure - which is not a pass and is not said as one - and otherwise ok. */
export type Standing =
  | { readonly kind: "error"; readonly count: number }
  | { readonly kind: "warning"; readonly count: number }
  | { readonly kind: "unchecked" }
  | { readonly kind: "ok" };

export function standingOf(findings: readonly ViolationView[]): Standing {
  const errors = findings.filter((one) => one.severity === "error").length;
  if (errors > 0) return { kind: "error", count: errors };
  const warnings = findings.filter((one) => one.severity === "warning").length;
  if (warnings > 0) return { kind: "warning", count: warnings };
  return findings.length > 0 ? { kind: "unchecked" } : { kind: "ok" };
}

const plural = (count: number, one: string): string => (count === 1 ? one : `${one}s`);

/** A standing as its badge reads: "2 errors", "1 warning", "not checked", "ok". */
export function standingWords(standing: Standing): string {
  switch (standing.kind) {
    case "error":
      return `${standing.count} ${plural(standing.count, "error")}`;
    case "warning":
      return `${standing.count} ${plural(standing.count, "warning")}`;
    case "unchecked":
      return "not checked";
    case "ok":
      return "ok";
  }
}

/** The part the status bar's count jumps to: the one with the most errors, then the one with
 * the most warnings, the first in the run's own order between two alike - or `null` when no
 * part has either, which leaves the project as the place to look. */
export function worstPart(parts: readonly PartView[], violations: readonly ViolationView[]): string | null {
  let worst: { ref: string; errors: number; warnings: number } | null = null;
  for (const part of parts) {
    const found = findingsOn(part.ref, violations);
    const errors = found.filter((one) => one.severity === "error").length;
    const warnings = found.filter((one) => one.severity === "warning").length;
    if (errors + warnings === 0) continue;
    if (
      worst === null ||
      errors > worst.errors ||
      (errors === worst.errors && warnings > worst.warnings)
    ) {
      worst = { ref: part.ref, errors, warnings };
    }
  }
  return worst?.ref ?? null;
}

/** Where the status bar's count goes (task-92): the part worst off, and the first place of its
 * first finding of the worst kind on it - an error when it has one, else a warning - that is on
 * that part, the place a person would click first in its list. `null` when no part is worse off
 * than ok, which leaves the project as the place to look. A finding with no place on the part
 * lights the part itself. */
export function worstPlace(
  parts: readonly PartView[],
  violations: readonly ViolationView[],
): { readonly part: string; readonly place: string } | null {
  const part = worstPart(parts, violations);
  if (part === null) return null;
  const found = findingsOn(part, violations);
  const severity = found.some((one) => one.severity === "error") ? "error" : "warning";
  const first = found.find((one) => one.severity === severity);
  return { part, place: first?.refs.find((ref) => within(ref, part)) ?? part };
}

/** What is selected, as the page holds it: the subject, and the ref lit in the view - the
 * subject's own ref, or a place of one of its findings. */
export interface Selection {
  readonly subject: Subject;
  readonly lit: string | null;
}

/** Whether a run names `ref`: a part it makes, or anything else it listed a ref for. */
const named = (ref: string, parts: readonly PartView[], refs: readonly string[]): boolean =>
  parts.some((part) => part.ref === ref) || refs.includes(ref);

/** The selection after a run that made `parts` and named `refs` (decision-12: selection is by
 * ref, so it survives a re-run when the ref still exists). A part stays the subject while the
 * run still makes it, and a face while the run still names it; either gone, the project is the
 * subject and nothing is lit - not the face's part, which nobody chose. A lit place the run no
 * longer names goes out, and the subject's own ref is lit instead. A reference mesh is not a
 * ref, and a run does not take it off the view, so it stays as it was.
 *
 * Whatever made the run - a script edit, a knob, the values file - the rule is the same: it
 * only reads what the newest run made. */
export function keptAcross(
  selection: Selection,
  parts: readonly PartView[],
  refs: readonly string[],
): Selection {
  const { subject, lit } = selection;
  if (subject.kind === "reference") return selection;
  const still = lit !== null && named(lit, parts, refs) ? lit : null;
  if (subject.kind === "project") return { subject, lit: still };
  if (!named(subject.ref, parts, refs)) return { subject: PROJECT, lit: null };
  return { subject: subjectOf(subject.ref, parts), lit: still ?? subject.ref };
}

/** A subject a link asks for: a part or a face, by ref - whether the run has it is the
 * scene's to say, once one arrives (`linkedIn`). */
export interface Linked {
  readonly kind: "part" | "face";
  readonly ref: string;
}

/** The URL hash that names `subject`, so a link opens on it: `#part=tote`,
 * `#face=tote/grip-left/top`, each segment of the ref escaped and its `/` left as they read.
 * The project, and a reference mesh - a file on the host rather than anything a run named -
 * are the empty hash. */
export function linkOf(subject: Subject): string {
  if (subject.kind !== "part" && subject.kind !== "face") return "";
  return `#${subject.kind}=${subject.ref.split("/").map(encodeURIComponent).join("/")}`;
}

/** What a URL hash asks to have selected, or `null` for a hash that asks for nothing this app
 * knows - empty, another key, or escaping that does not decode - which is simply the project. */
export function linked(hash: string): Linked | null {
  const text = hash.startsWith("#") ? hash.slice(1) : hash;
  const equals = text.indexOf("=");
  if (equals === -1) return null;
  const kind = text.slice(0, equals);
  if (kind !== "part" && kind !== "face") return null;
  let ref: string;
  try {
    ref = text.slice(equals + 1).split("/").map(decodeURIComponent).join("/");
  } catch {
    return null;
  }
  return ref === "" ? null : { kind, ref };
}

/** The subject a link's ask makes in a run that made `parts` and named `refs`: the ref as
 * `subjectOf` reads it when the run names it - so a `#face=` that is a part's own ref is the
 * part - and otherwise the project, quietly: a link to something since renamed is not an
 * error, it is somewhere to start. */
export function linkedIn(asked: Linked | null, parts: readonly PartView[], refs: readonly string[]): Subject {
  if (asked === null || !named(asked.ref, parts, refs)) return PROJECT;
  return subjectOf(asked.ref, parts);
}

/** A part's ref as a Python identifier, the way a maker would type it by hand: `-` turned to
 * `_`, a leading digit given a `_` to sit behind. It stands in for the script's own `Part`
 * variable, which the app has no way to know (decision-7: a pick writes numbers, never a
 * script's own names) - so it is the most useful honest guess, right when a part's variable
 * is named after its label and wrong otherwise, and *Insert fit*'s line still needs reading
 * before it is trusted, the same as any inserted `ref("…")` needing the right hole to sit in. */
export function fitIdentifier(ref: string): string {
  const cleaned = ref.replaceAll(/[^A-Za-z0-9_]/g, "_");
  return /^[0-9]/.test(cleaned) ? `_${cleaned}` : cleaned;
}

/** The `mated(...)` line a pair of picked faces would write - task-61's *Insert fit* - or why
 * it cannot: a part with no body (sheet, not print), or a face `plane_of` cannot frame (round,
 * no `around=`), each say so rather than writing a call that only fails once the script runs.
 * `{ why: "" }` while there is no pair to speak of. */
export function fitLine(
  first: string | null,
  second: string | null,
  parts: readonly PartView[],
): { readonly text: string } | { readonly why: string } {
  if (first === null || second === null) return { why: "" };
  const fixed = partOf(first, parts);
  const moving = partOf(second, parts);
  if (fixed === null || moving === null) return { why: "" };
  if (fixed.process !== "print" || moving.process !== "print") {
    return { why: "mated puts one printed part's face on another's; a sheet part has none" };
  }
  if (fixed.frames[first] === undefined) {
    return { why: `${first} has no single plane - plane_of needs around= for a round face` };
  }
  if (moving.frames[second] === undefined) {
    return { why: `${second} has no single plane - plane_of needs around= for a round face` };
  }
  const text = `mated(${fitIdentifier(fixed.ref)}, ref(${JSON.stringify(first)}), ${fitIdentifier(moving.ref)}, ref(${JSON.stringify(second)}))`;
  return { text };
}
