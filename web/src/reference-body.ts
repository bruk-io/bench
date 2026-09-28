/** The reference mesh on the view: a body somebody else made, held while a script copies it -
 * its survey, the faces detected on it, and decision-7's pick that turns a click on one of them
 * into the project's `[reference]` placement.
 *
 * Moved out of `main.ts` (task-88) when its controls moved out of the view and into the
 * inspector: this is the state those controls show and the acts they ask for, and `view()` is
 * what `bench-reference-tools` draws. What it cannot know - the workspace, the worker, the
 * editor group - is the page's, handed in as `BodyHost`; reading and writing the mesh's file on
 * the host stays in `main.ts` too, since it is about the project's directory rather than the
 * body on the view.
 *
 * **Nothing measured in one frame is kept in another.** A placement arriving or leaving, a new
 * body, a project that places the same body differently - each drops every detection and pick
 * and asks again, the same rule `bench.worker.detected` follows for a survey, one layer up.
 */
import type { DetectOutcome, SurveyOutcome } from "./bridge";
import type { PickView, ReferenceToolsView } from "./components/organisms/reference-tools";
import { log } from "./telemetry";
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
import { type ReferenceTable, type ReferenceValue, placing } from "./values";
// A type only: `viewer3d` itself is fetched when the first scene lands (`deferred3d`), and a
// type import is erased, so naming the shape a pick comes back as costs the bundle nothing.
import type { DetectHit } from "./viewer3d";

/** What the body needs of the page. */
export interface BodyHost {
  /** Colour the backdrop by detected flat, or stop (`null`). */
  detectOnView(flatIndex: readonly (number | null)[] | null): void;
  /** Ask the worker to survey, or detect the faces of, `reference` under `table`. */
  survey(reference: string, table: string | undefined): void;
  detect(reference: string, table: string | undefined): void;
  /** Run the script now, with whatever body is on the view. */
  runNow(): void;
  /** The open project's `[reference]` table, as it stands. */
  placement(): ReferenceTable | null;
  /** Write the open project's `[reference]` table - `null` to drop it. */
  place(table: ReferenceTable | null): void;
  /** Whether this tab may write the open project (task-47). */
  writable(): boolean;
  /** Open the survey's report beside the script, or close it. */
  openReport(): void;
  closeReport(): void;
  /** Something the tools show has changed. */
  changed(): void;
}

/** One flat `bench.worker.detected` found, in the terms it answered with - a plain view of
 * `bench.survey.Flat`, not the class itself, since this crossed the wire as JSON. */
interface DetectedFlat {
  readonly normal: readonly [number, number, number];
  readonly centre: readonly [number, number, number];
  readonly area: number;
}

const HOW_TO_PICK = "Click a coloured face: what it measures reads here.";

const PLACED_FRAME =
  "This body is already placed by the open project's [reference], so every number here is " +
  "in the placed frame. Clear the placement to pick against the body as exported.";

/** `bytes` as base64, a chunk at a time: spreading a megabyte into `fromCharCode` at once
 * overflows the call stack, and a dropped body is comfortably a megabyte. */
function encoded(bytes: Uint8Array): string {
  let text = "";
  for (let at = 0; at < bytes.length; at += 0x8000) {
    text += String.fromCharCode(...bytes.subarray(at, at + 0x8000));
  }
  return btoa(text);
}

/** The body on the view, and everything measured about it - one per page. */
export function referenceBody(host: BodyHost) {
  /** Read once, held as base64, and handed to every run after it as `reference`, so a script
   * can measure the thing it is copying - `survey(reference)` - while it writes the thing that
   * replaces it. A second drop replaces the first. */
  let reference: string | null = null;
  /** What the body was called, which is what its report's tab is called. */
  let name = "";
  /** Why the body is not in the open project's directory, when it is not - the route's
   * refusal, in its words. `null` for a body that landed, or is on its way. */
  let problem: string | null = null;
  /** The survey, written out - asked of the worker once per body and frame, and kept for as
   * long as the body is, so its tab can be shut and opened again without measuring twice.
   * `null` while there is no body, or while the worker is at it. */
  let report: string | null = null;
  /** The survey could not be made; the run's own failure has said why. */
  let unsurveyed = false;
  /** Whether the survey on its way is one nobody asked to read - a body put back because the
   * project's `[reference]` names it - so its report waits behind the button. */
  let quietly = false;
  /** Whether the view is colouring the body's detected faces, and whether the worker is still
   * finding them. */
  let detecting = false;
  let waiting = false;
  /** The flats a detection last found, indexed the way `detect`'s own array is - or `null`
   * while nothing has been detected. */
  let flats: readonly DetectedFlat[] | null = null;
  /** The three points this body's own `origin` words name, as the detection reported them,
   * and the distance within which a picked point *is* one of them - `bench.survey.ROUND`, read
   * off the wire rather than held here, so the snap and the survey can never hold two figures. */
  let origins: readonly NamedOrigin[] = [];
  let round = 0;
  /** The last two picks, newest first - two because the distance between two picked faces is
   * how a maker measures a wall. */
  let picks: readonly DetectHit[] = [];
  let read = HOW_TO_PICK;
  let fields = { origin: "", up: "", along: "" };
  let why = "";
  let whyBad = false;
  /** What choosing another reference did to `[reference]`, when it did more than name it. */
  let said = "";

  /** The open project's `[reference]` table as a placement of this body - or `null` when there
   * is no body, the project places nothing, the table only names which mesh is active
   * (`placing`), or it is about another file. decision-4's rule: a placement for one file is
   * never applied because a different one happens to be on the view. */
  function matched(): ReferenceTable | null {
    if (name === "") return null;
    const table = host.placement();
    if (table === null || table["file"] !== name || !placing(table)) return null;
    return table;
  }

  /** `matched()`, as the JSON text the worker takes - or `undefined` for nothing to place with,
   * which a run and a survey both take to mean "hand over the mesh exactly as exported". */
  const tableJson = (): string | undefined => {
    const table = matched();
    return table === null ? undefined : JSON.stringify(table);
  };

  function say(text: string, bad = false): void {
    why = text;
    whyBad = bad;
  }

  /** While the project places this body, every number the pick reads is in the placed frame,
   * which is not the one `[reference]` asks for: said, whenever the pick is looked at again. */
  function refresh(): void {
    if (matched() !== null) say(PLACED_FRAME);
    host.changed();
  }

  /** Every detection and pick of the old frame, dropped. */
  function unmeasure(): void {
    flats = null;
    origins = [];
    round = 0;
    picks = [];
    host.detectOnView(null);
  }

  /** One flat as the readout says it. */
  function saidFlat(flatIndex: number | null): string {
    const flat = flatIndex === null ? undefined : flats?.[flatIndex];
    if (flat === undefined || flatIndex === null) return "no detected face here";
    return `flat ${flatIndex} · ${flat.area.toFixed(1)} mm²\nnormal ${shown(flat.normal, 4)} · centre ${shown(flat.centre)}`;
  }

  /** How far this pick is from the one before it - the wall-thickness line: between the two
   * points clicked, and, when both landed on a detected face, between those faces' own
   * centres, which is the number a caliper would give. */
  function saidSpan(hit: DetectHit): string {
    const before = picks[1];
    if (before === undefined) return "";
    const lines = [`from the pick before: ${mm(between(hit.point, before.point))}`];
    const here = hit.flatIndex === null ? undefined : flats?.[hit.flatIndex];
    const there = before.flatIndex === null ? undefined : flats?.[before.flatIndex];
    if (here !== undefined && there !== undefined && hit.flatIndex !== before.flatIndex) {
      lines.push(`face centre to face centre: ${mm(between(here.centre, there.centre))}`);
    }
    return `\n${lines.join("\n")}`;
  }

  /** Fill a field with a resolved value, and say what it resolved to and why. */
  function assigned(field: "origin" | "up", value: ReferenceValue, what: string): void {
    fields = { ...fields, [field]: fieldText(value) };
    const how =
      typeof value === "string"
        ? `it is within ${mm(round, 4)} of the point that word names, so the word is what is written`
        : "the numbers it measured";
    say(`${what} = ${fieldText(value)}: ${how}.`);
    host.changed();
  }

  /** A placement arrived or left: the body's frame changed under everything already measured
   * about it, so every measurement is dropped and asked for again under the new frame - the
   * faces, if they were being shown, the survey, and the run that draws the body. */
  function replaced(because: string): void {
    const again = detecting && reference !== null;
    unmeasure();
    read = HOW_TO_PICK;
    report = null;
    unsurveyed = false;
    waiting = again;
    log("info", "bench.reference", because);
    host.runNow();
    if (reference !== null) host.survey(reference, tableJson());
    if (again && reference !== null) host.detect(reference, tableJson());
    refresh();
  }

  return {
    /** The body as base64, for the run - `null` while there is none. */
    reference: (): string | null => reference,
    /** The body's file name, `""` while there is none. */
    name: (): string => name,
    report: (): string | null => report,
    tableJson,
    matched,
    refresh,

    /** Make `bytes`, called `file`, the body on the view: measured, run against, surveyed.
     * `quiet` for a body the app put back by itself rather than one a person dropped: the run
     * and the survey are the same, but the report waits behind its button instead of opening.
     * `run` false holds it for the next run without starting one - for a page that is holding
     * a script back because it ran away last time (task-96), which still has to be handed the
     * body its project names when somebody does press Run. */
    hold(file: string, bytes: Uint8Array, quiet: boolean, run = true): void {
      reference = encoded(bytes);
      name = file;
      problem = null;
      report = null;
      unsurveyed = false;
      said = "";
      // A new body invalidates any detection of the last one: its triangles are not this
      // one's, so detection goes off rather than colour the wrong mesh's flats onto this one.
      detecting = false;
      waiting = false;
      unmeasure();
      log("info", "bench.reference", quiet ? "a reference was read back from the project" : "a body was put on the view", {
        "bench.reference.name": file,
        "bench.reference.bytes": bytes.length,
      });
      // The run first, so the view shows the body at once; the survey follows it in the worker
      // and its report opens when it lands. A drop is the maker asking what the body measures,
      // so it is not made to ask twice.
      if (run) host.runNow();
      quietly = quiet;
      host.survey(reference, tableJson());
      refresh();
    },

    /** Forget the body: its report goes with it, and the next run draws the work on its own -
     * the re-run is the point, or the backdrop would stay until something else ran. */
    forget(): void {
      reference = null;
      name = "";
      report = null;
      unsurveyed = false;
      said = "";
      detecting = false;
      waiting = false;
      unmeasure();
      host.closeReport();
      host.runNow();
      refresh();
    },

    /** The project's directory would not take the body, in the route's words. */
    notKept(because: string): void {
      problem = because;
      host.changed();
    },

    /** What choosing another reference did to `[reference]`, or `""`. */
    choseSaying(text: string): void {
      said = text;
      host.changed();
    },

    /** The survey came back: the report opens beside the script - or, when there is none, the
     * button says so, and the run's own failure, which put the same file through the same
     * reader, has already said why. */
    surveyed(outcome: SurveyOutcome): void {
      if (reference === null) return; // taken off while the worker was at it
      if ("problem" in outcome) {
        log("warn", "bench.reference", "the dropped body was not surveyed", { "error.message": outcome.problem });
        unsurveyed = true;
        host.changed();
        return;
      }
      report = outcome.report;
      host.changed();
      if (quietly) quietly = false;
      else host.openReport();
    },

    /** Detection on or off. Off turns the backdrop back into a plain ghost at once; on asks the
     * worker for the body's flats. Detection is also the pick's own mode (decision-7): the
     * panel comes and goes with it, because the backdrop answers a click only while it is on. */
    toggleDetect(): void {
      if (reference === null) return;
      if (detecting) {
        detecting = false;
        waiting = false;
        host.detectOnView(null);
        refresh();
        return;
      }
      detecting = true;
      waiting = true;
      host.detect(reference, tableJson());
      refresh();
    },

    /** The detection came back: the backdrop is coloured by it - or, when there is none,
     * detection goes back off and says why in the log. */
    detected(outcome: DetectOutcome): void {
      if (reference === null || !detecting) return; // taken off, or turned off, meanwhile
      waiting = false;
      if ("problem" in outcome) {
        log("warn", "bench.reference", "the dropped body's faces were not detected", {
          "error.message": outcome.problem,
        });
        detecting = false;
        host.changed();
        return;
      }
      const found = JSON.parse(outcome.result) as {
        flat_index: readonly (number | null)[];
        flats: readonly DetectedFlat[];
        origins: readonly NamedOrigin[];
        round: number;
      };
      flats = found.flats;
      origins = found.origins;
      round = found.round;
      host.detectOnView(found.flat_index);
      refresh();
    },

    /** A project was opened: a body already on the view may be placed differently - or not at
     * all - by it, so the report is asked again, and a detection made under the project just
     * left is turned off rather than left showing faces at the wrong numbers. */
    reopened(): void {
      if (reference === null) return;
      report = null;
      unsurveyed = false;
      host.survey(reference, tableJson());
      if (detecting) {
        detecting = false;
        waiting = false;
        flats = null;
        host.detectOnView(null);
      }
      refresh();
    },

    /** A detected face was clicked: everything the click resolved to, in the pick and the log.
     * Numbers only - a measurement is never turned into script text here, which is task-14.3
     * and decision-7's own position, not a limitation of this panel. */
    picked(hit: DetectHit | null): void {
      if (hit === null) {
        read = "That click met the body nowhere. Click a coloured face.";
        host.changed();
        return;
      }
      picks = [hit, ...picks].slice(0, 2);
      const away = distances(hit.vertex, origins)
        .map((one) => `${one.name} ${mm(one.away)}`)
        .join(" · ");
      read =
        `${saidFlat(hit.flatIndex)}\n` +
        `hit ${shown(hit.point)}\n` +
        `corner ${shown(hit.vertex, 4)}\n` +
        `corner from ${away}${saidSpan(hit)}`;
      log("info", "bench.pick", "a face was picked", {
        // A word rather than a number for "no face here": a sentinel index would read as a face.
        "bench.pick.flat": hit.flatIndex === null ? "none" : String(hit.flatIndex),
        "bench.pick.point": hit.point.join(", "),
        "bench.pick.corner": hit.vertex.join(", "),
      });
      refresh();
    },

    /** One of the pick's three assignments.
     *
     * *origin = hit* is the point the ray met - the general case decision-7 describes.
     * *origin = corner* is the nearest corner of the face clicked, which is what makes a named
     * word reachable at all: on an axis-aligned box `Extent.low` *is* one of the mesh's own
     * vertices, where no mouse lands within a hundredth of a millimetre of anything.
     * *up = this face* is the face's own normal, always as the triple it measured, never
     * snapped to a signed axis word: that would need a tolerance on an angle, and decision-7
     * says plainly that bench has none to borrow. */
    assign(how: "origin" | "corner" | "up"): void {
      const hit = picks[0];
      if (hit === undefined) return;
      if (how === "origin") {
        assigned("origin", resolvedOrigin(hit.point, origins, round), "origin");
        return;
      }
      if (how === "corner") {
        assigned("origin", resolvedOrigin(hit.vertex, origins, round), "origin");
        return;
      }
      const flat = hit.flatIndex === null ? undefined : flats?.[hit.flatIndex];
      if (flat === undefined) return;
      assigned("up", resolvedUp(flat.normal), "up");
    },

    /** A field typed into. */
    typed(field: "origin" | "up" | "along", text: string): void {
      fields = { ...fields, [field]: text };
    },

    /** Commit: the three fields become the open project's `[reference]` table, in one act.
     *
     * One act rather than a write per pick, which task-18.2's rule for `[values]` would
     * suggest: a `[reference]` table is applied the moment its `file` names the body, and from
     * there every run, survey and detection puts the mesh through `bench.placement.placement`,
     * which *raises* on a table missing any of `origin`, `up` or `along` - a per-field write
     * would break the run between the first pick and the last, and move the body the second
     * pick is measured against. decision-7 left this open; this is the answer, and it is the
     * code's, not a preference. */
    write(): void {
      if (name === "" || !host.writable()) return;
      const origin = fieldValue(fields.origin);
      const up = fieldValue(fields.up);
      const along = fieldValue(fields.along);
      if (origin === null || up === null || along === null) {
        const missing = [
          origin === null ? "origin" : null,
          up === null ? "up" : null,
          along === null ? "along (typed - decision-7 designs no edge-pick)" : null,
        ].filter((one) => one !== null);
        say(
          `A placement is all three or none, because the run refuses a partial table: ${missing.join(", ")} still to say.`,
          true,
        );
        host.changed();
        return;
      }
      host.place({ file: name, origin, up, along });
      log("info", "bench.pick", "a placement was written", {
        "bench.reference.name": name,
        "bench.pick.origin": fieldText(origin),
        "bench.pick.up": fieldText(up),
        "bench.pick.along": fieldText(along),
      });
      // The body now moves, so nothing measured in the old frame is worth keeping on screen.
      replaced("the placement was written");
      say("Written. The body is placed by it now - the view, the survey and the chip all say so.");
      host.changed();
    },

    /** Forget the placement, so a pick reads the body as exported again - the way back out of
     * the placed frame, and the only way to re-pick a placement this panel wrote. */
    unplace(): void {
      if (!host.writable()) return;
      host.place(null);
      replaced("the placement was cleared");
      say("Cleared. The body stands as exported, and a pick reads its own numbers again.");
      host.changed();
    },

    /** What `bench-reference-tools` draws - `null` while there is no body. */
    view(): ReferenceToolsView | null {
      if (name === "") return null;
      const placed = matched() !== null;
      return {
        chip: `${name}${placed ? " · placed" : ""}${problem === null ? "" : " · not kept"}`,
        chipTitle: problem === null ? "" : `not kept in the project: ${problem}`,
        survey: report !== null ? "ready" : unsurveyed ? "none" : "measuring",
        detecting,
        detectWaiting: waiting,
        pick: detecting && reference !== null ? pickView(placed) : null,
        said,
      };
    },
  };

  /** The pick panel's own state: its assign buttons live once something has been picked, and
   * its write refused while a placement is already applied - because then the view, the survey
   * and the detection are all in the placed frame, and a number picked there is not the number
   * `[reference]` asks for, which is the mesh's own. A reader picks and reads every number, and
   * writes none of them (task-47). */
  function pickView(placed: boolean): PickView {
    const hit = picks[0];
    const flat = hit === undefined || hit.flatIndex === null ? undefined : flats?.[hit.flatIndex];
    return {
      frame: placed ? "reading the placed frame" : "",
      read,
      canOrigin: hit !== undefined && !placed,
      canCorner: hit !== undefined && !placed,
      canUp: flat !== undefined && !placed,
      canWrite: !placed && host.writable(),
      placed,
      canUnplace: host.writable(),
      ...fields,
      why,
      whyBad,
    };
  }
}

export type ReferenceBody = ReturnType<typeof referenceBody>;
