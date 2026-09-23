/** What the status line and the viewer's hints say, in words, from facts the scene carries.
 *
 * Python counts: how many parts and sheets, how many errors and warnings, the first failing
 * line, and how many parts have a body to draw and how many do not. This module only puts
 * those numbers into words, so nothing here filters or counts a scene. Every function is pure,
 * which is what makes the wording testable on its own.
 */
import type { SummaryView } from "./scene";

const plural = (count: number, one: string): string => (count === 1 ? one : `${one}s`);

/** What a run made, in words - "14 parts on 7 sheets", or "1 part" when nothing is cut - and
 * what its checks found, so a run that succeeded and is still wrong says so up top rather
 * than only in a panel that may be scrolled out of sight. */
export function tally(summary: SummaryView): string {
  const parts = `${summary.parts} ${plural(summary.parts, "part")}`;
  const made =
    summary.sheets === 0
      ? parts
      : `${parts} on ${summary.sheets} ${plural(summary.sheets, "sheet")}`;
  const found = [
    ...(summary.errors === 0 ? [] : [`${summary.errors} ${plural(summary.errors, "error")}`]),
    ...(summary.warnings === 0
      ? []
      : [`${summary.warnings} ${plural(summary.warnings, "warning")}`]),
  ];
  return [made, ...found].join(" · ");
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

/** What a tab that is only reading `project` says, and why: the notice's title and its text,
 * and the status bar's short word. `lost` when this tab was the writer and somebody took it
 * over - the one time the person has to be told something changed under them (task-47). */
export function readOnlyWords(
  project: string,
  holder: Holder,
  lost: boolean,
): { readonly title: string; readonly text: string; readonly chip: string; readonly chipTitle: string } {
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
  return { title, text, chip: "read-only", chipTitle: `${project} is being written by ${who}` };
}
