/** What the status line and the viewer's hints say, in words, from facts the scene carries.
 *
 * Python counts: how many parts and sheets, how many errors and warnings, the first failing
 * line, and how many parts have a body to draw and how many do not. This module only puts
 * those numbers into words, so nothing here filters or counts a scene. Every function is pure,
 * which is what makes the wording testable on its own.
 */
import type { SummaryView } from "./scene";

const plural = (count: number, one: string): string => (count === 1 ? one : `${one}s`);

/** What a run made, in words - "14 parts on 7 sheets", or "1 part" when nothing is cut - for
 * the status line. What its checks found is said beside it, as the count that goes to them
 * (`found`, decision-12), so a run that succeeded and is still wrong says so up top rather
 * than only in a list that may be scrolled out of sight. */
export function built(summary: SummaryView): string {
  const parts = `${summary.parts} ${plural(summary.parts, "part")}`;
  return summary.sheets === 0 ? parts : `${parts} on ${summary.sheets} ${plural(summary.sheets, "sheet")}`;
}

/** What a run's checks found, counted - "1 error · 2 warnings" - or `""` for nothing. What
 * nothing could measure is not counted: it is not a finding, and not a pass either. */
export function found(summary: SummaryView): string {
  return [
    ...(summary.errors === 0 ? [] : [`${summary.errors} ${plural(summary.errors, "error")}`]),
    ...(summary.warnings === 0 ? [] : [`${summary.warnings} ${plural(summary.warnings, "warning")}`]),
  ].join(" · ");
}

/** What a run made, counted for the chip beside the file name: no findings, because the
 * status bar says those, and a chip that grew a clause would stop being a glance. */
export function made(summary: SummaryView): string {
  const parts = `${summary.parts} ${plural(summary.parts, "part")}`;
  if (summary.sheets === 0) return parts;
  return `${parts} · ${summary.sheets} ${plural(summary.sheets, "sheet")}`;
}

/** Whether any check found something that will not work. */
export const failing = (summary: SummaryView): boolean => summary.errors > 0;

/** How to get a ref, said while nothing is selected: every face, engraved line and line of
 * lettering in the view answers to one. */
export const HOW_TO_SELECT = "click any face to get its ref";

/** Why the view is empty, when a scene has parts and none of them has a body to draw; `""`
 * otherwise. A laser part is always drawn, so what is left is a printed part in a run whose
 * modeller did not load. */
export function noBodiesReason(summary: SummaryView): string {
  if (summary.unbuilt === 0 || summary.solid > 0) return "";
  return (
    `${summary.unbuilt} ${plural(summary.unbuilt, "part")}, but this run built no body to` +
    " draw: the modeller did not load. Refs, parameters and cut sheets are unaffected."
  );
}

/** A span of time as a person says it roughly: "a moment", "40 seconds", "3 minutes",
 * "2 hours". */
export function roughly(ms: number): string {
  const seconds = Math.round(ms / 1000);
  if (seconds < 5) return "a moment";
  if (seconds < 90) return `${seconds} seconds`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `${minutes} ${plural(minutes, "minute")}`;
  const hours = Math.round(minutes / 60);
  return `${hours} ${plural(hours, "hour")}`;
}

/** Who holds a project's write lease, as a reader is shown it - `lease.ts`'s `Held`. */
interface Holder {
  readonly label: string;
  readonly address: string;
  readonly forMs: number;
  readonly heardAgoMs: number;
}

/** Everything a tab that is only reading a project says about it (`readOnlyWords`). */
export interface ReadOnlyWords {
  /** The header chip's own words - short, since the rest is one click away (task-91) - and
   * the part of them after `chip`'s word, which a narrow header leaves off. */
  readonly badge: string;
  readonly badgeWhy: string;
  /** The chip's popover: whose it is and where, then for how long and what a reader can do. */
  readonly title: string;
  readonly text: string;
  /** What Take over asks before it takes the project from somebody. */
  readonly confirm: string;
  /** The status bar's short word, and what it says on hover. */
  readonly chip: string;
  readonly chipTitle: string;
}

/** What a tab that is only reading `project` says, and why: the header chip, its popover's
 * title and text and the question Take over asks, and the status bar's short word. `lost` when
 * this tab was the writer and somebody took it over - the one time the person has to be told
 * something changed under them (task-47). */
export function readOnlyWords(project: string, holder: Holder, lost: boolean): ReadOnlyWords {
  const who = `${holder.label} at ${holder.address}`;
  const title = lost
    ? `${who} took over writing ${project}. It is read-only here now.`
    : `${project} is open for writing in ${who}, so it is read-only here.`;
  const since = lost
    ? `It took it ${roughly(holder.forMs)} ago`
    : `It has held it for ${roughly(holder.forMs)}`;
  const text =
    `${since}, and was last heard from ${roughly(holder.heardAgoMs)} ago. Here you can open, run and ` +
    "export it, and turn its knobs to see what they do - but nothing you change is kept: not the " +
    "script, not a knob, not a placement. It becomes yours by itself once that one lets go.";
  const confirm =
    `Take ${project} from ${who}? From then on it can keep nothing: an edit it has not saved yet ` +
    "is refused, and it is told you took it over. Do this when that one is somewhere you cannot reach.";
  const badgeWhy = lost ? "taken over" : "held elsewhere";
  return {
    badge: `read-only · ${badgeWhy}`,
    badgeWhy,
    title,
    text,
    confirm,
    chip: "read-only",
    chipTitle: `${project} is being written by ${who}`,
  };
}
