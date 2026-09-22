---
id: task-18.2
title: 'Make a project a thing the app keeps, not a string in a browser'
status: Done
assignee: []
created_date: '2026-09-22 21:06'
updated_date: '2026-09-22 02:04'
labels:
  - web
  - project
dependencies:
  - task-18.1
parent_task_id: task-18
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The app's kept file is name, source and overrides in localStorage, and the overrides are a JSON blob nobody can read, diff or send. This turns that half into a document: the same three things, with the values as TOML.

The parameters container stops being a scratchpad and becomes an editor for a file - the knob you turned becomes a line somebody can read in a diff. The file opens as a tab beside the script in the editor group, being a document like a cut sheet.

This is the expensive half of decision-3. The app's file model becomes a project model, which reaches files.ts, storage.ts, the files container, the export path and a good part of the e2e suite. It is worth doing after the command-line host has proved the shape, not before.

Two of decision-3's open questions have to be answered here rather than assumed: whether the panel writes on every edit or on a save, and whether a value the run clamped is written back clamped or left as the maker typed it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A project's values survive being opened somewhere else, which is what browser storage cannot do
- [x] #2 Editing a parameter changes the values, and those values are what the next run uses
- [x] #3 The values are readable as a document, not only through the panel
- [x] #4 A project whose values file is missing still opens and runs on the script's defaults
- [x] #5 Renaming, deleting and duplicating a project keep the script and its values together
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Shape

The kept record grows from `{ name, source, overrides }` to `{ name, source, values }`, where `values` is the TOML text `tools/build.py` already reads - `[values]` with one line per set field. In memory the page keeps the table (`Overrides`) as it does today; the TOML is what it is kept as, shown as, and sent as. `files.ts` stays pure (no DOM, no storage) and keeps its two invariants.

- `web/src/values.ts` (new, pure): `valuesName(script)` (`cabinet.py` -> `cabinet.toml`), `document(table, script, order)` writes the TOML, `read(text)` reads the `[values]` table of one back - a subset reader (bare/quoted keys, ints, floats, booleans, basic and literal strings, comments; other tables skipped so `[[measured]]` is not an error later) that names the line it cannot read.
- `files.ts`: `ScriptFile` becomes `Project`; `serialized`/`restored` carry the values as TOML and still read a record kept with the old JSON `overrides` or with nothing (criterion 4); `created` takes values; `duplicated` copies script and values under a free name.
- `overrides.ts`: `asBuilt(table, values)` - the table with each set name replaced by what the run built.
- `main.ts`: a second permanent tab in the editor group, `<stem>.toml`, showing the document (criterion 3); the explorer gains Duplicate, Save (a zip of the two files) and Open… (a `.py` with its `.toml` beside it, or a `.toml` for the open project) - criteria 1 and 5.
- e2e: the kept values are read back with `tomllib`; a downloaded project is run by `tools.build.main` outside the browser (criterion 1 proved by the other host, not asserted).

## The two open questions

**Write on every edit.** The app has no save anywhere - every keystroke in the script is kept - so a save for the values alone would be the one save button in the app, and the file would then be truthful only after a click. The file is the truth and the panel is a view of it. The "noisier diff" cost is real only where there is a diff, and the browser has none: the moment a project reaches a repository is the download, which is already a deliberate act.

**Written back as built.** A value the run held to its range is copied back from `scene.values` - Python's own answer, so the rule lives in `params.py` once and TS mirrors nothing. It is safe because `bridge.ts` drops superseded scenes (`id !== latest`), so a scene answers the latest request; the copy-back happens only when the table is still the one that request was sent with, which is exactly the guard the mid-debounce test wants. Cost: a maker who typed 9 against `max=7` sees 7 and the file says 7; the intent past the range is lost, and the place to change the range is the script one tab over.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch `project-in-the-app`, PR against main - not merged; the owner verifies.

**What was built.** `web/src/values.ts` (new, pure) writes the `[values]` table as TOML and reads it back with a subset reader that names the line it cannot read and passes other tables over unread. `files.ts` stays pure with its two invariants; the kept record is `{ name, source, values }` with `values` the TOML text, and a record from before (`overrides` object) or with nothing is still read. `duplicated` copies script and values together. The editor group has a permanent `<script>.toml` tab beside the script. The explorer is "Projects" and gains Duplicate, Download (script + `.toml` in one zip - the pair `tools.build` runs) and Open… (`.py` with the `.toml` beside it, or a `.toml` alone for the open project); a pick with an unreadable values file opens nothing and names the line. Nothing under `src/bench` changed; no dependency added.

**Open question 1 - write on every edit.** The app has no save anywhere (every keystroke of the script is kept), so a save for the values alone would be the app's one save button and the file truthful only after a click. The file is the truth, the panel a view of it. The diff-noise cost exists only where there is a diff, and the browser has none: a project reaches a repository by the download, which is a deliberate act.

**Open question 2 - written back as built.** `asBuilt(table, scene.values)` copies Python's own answer back, so a value held to its range is kept as built; the rule lives in `params.py` once and TS mirrors nothing. Safe because `bridge.ts` drops superseded scenes, so a scene answers the latest request, and the copy-back happens only while the table is still the one that request was sent with - the mid-debounce guard the e2e already insists on. Cost: intent past the range is lost; the range is the script's, one tab over. In practice the panel already holds a typed number at its end on commit, so this matters for a file opened from disk and a script whose range moved.

**A third question decision-3 missed.** Is the TOML a document the maker owns or a rendering the app owns? Here a rendering: regenerated from the table on every edit, so a hand-written comment in an opened `.toml` does not survive the first panel edit, and the tab is read-only for that reason. Editing the file in the app would make the text the truth and is a decision of its own.

**Where the brief was optimistic.** The params container did not change at all - it never kept the table. The export path did not change - the project download is a new path through `downloads.zip`.

**Criteria, checked rather than assumed.** #1: a downloaded project is unzipped and run by `tools.build.main` in the e2e, with no browser, and reports `shelf-2.toml: w=150`; and a project opened from disk arrives with its values. #2: `w = 150` set in the panel is the kept file and the next run's geometry. #3: the `.toml` tab, read as a document by `tomllib` in the e2e. #4: a `.py` opened with no `.toml` runs on defaults with an empty `[values]`; a kept record with no values does the same (unit test). #5: rename renames the tab, duplicate carries `w = 150`, delete removes the project as a whole.

**Gate.** `uv run tools/check.py` in full, twice, in a worktree with `npm ci` and `npm run generate` done first, so nothing was skipped: tsc, eslint + lit-analyzer, 167 component tests, 690 pytest x2, `65 passed` e2e (six new), `ALL CHECKS PASSED`.

Merged as 17c82f5 (PR #21, squashed). Verified before merge: the branch was based on be870bb and gated at 65 e2e, predating #20's test. Rebased onto 5f356e8 by the agent; full gate green at 66 e2e (60 on main + 6 new), 169 component, 690 pytest x2. The rebased push was refused by permissions, so rather than forcing it, the squash-merge tree was compared against the gated commit's tree - both 276aedc3bce07a0385dd2e2fd7501435874b3ba5 - confirming GitHub's merge landed exactly what was tested.

Three questions the work raised, left open for the owner: (1) values are written on every edit, there being no save anywhere in the app; (2) values are written back as built, so a range-clamped value is stored clamped rather than as typed; (3) decision-3 never asked whether the TOML is a document the maker owns or a rendering the app owns - this implements it as a rendering, so hand-written comments in an opened .toml do not survive the first panel edit, and the tab is read-only for that reason. Making the text the truth would be its own decision.
<!-- SECTION:NOTES:END -->
