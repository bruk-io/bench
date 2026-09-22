---
id: task-19
title: 'Reach the survey from the app, not only from a typed call'
status: Done
assignee: []
created_date: '2026-09-22 02:46'
updated_date: '2026-09-22 03:05'
labels:
  - feature
  - web
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
task-14 built the whole measuring half and a maker cannot find it. `survey` and `report` are exported from `bench`, but nothing in `web/` calls them - the only mention in `main.ts` is a comment in a docstring. The only way to use any of it today is to drop an STL as a reference mesh and then type `print(report(survey(reference)))` into the script yourself, which means knowing the two verbs exist and knowing the reference is in scope.

The drop already works and the mesh already arrives as `reference`. What is missing is anything that says so: a way to ask for the survey of what was just dropped, and somewhere for a report of a few hundred lines to be read.

Worth deciding rather than assuming: whether the report belongs in the bottom panel as a tab beside problems and output, or opens as a document tab in the editor group the way `<script>.toml` now does. The report is a document a reader works through and refers back to while writing the script beside it, which argues for the editor group; it is also output of a run, which argues for the panel. It is long - 129 lines for the simplest real part read so far, 589 for the handle - so wherever it goes it must be scrollable and must not push the script out of the way.

Nothing about the measuring needs to change for this: it is a UI task against two functions that are already tested and already honest about their limits.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A maker who drops a mesh can get its report without typing a call or knowing the verbs exist
- [x] #2 The report is readable at the length real parts produce - hundreds of lines - without hiding the script
- [x] #3 The survey runs on the dropped reference mesh without a solid modeller, as it does from a script
- [x] #4 Nothing under src/bench changes to support it
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read survey.py's "What counts as what", report.py's rules, and the drop path (main.ts -> bridge -> worker.ts -> bench/worker.py -> script.run(reference=...)).
2. Decide placement: editor-group document tab (see notes for why, and what the panel would have cost).
3. worker.ts: a `survey` request type with a queue slot of its own; a SURVEY entry composing bench.mesh_from_stl / bench.survey / bench.report - nothing under src/bench changes.
4. bridge.ts: `survey(stl)` and `onSurvey(outcome)`; a pending survey is reported lost when the worker is replaced.
5. main.ts + index.html + styles.css: a drop asks for the survey after the run; the report opens as a closable `bracket.stl` tab beside the script; the reference chip gets a `survey` button that reads `measuring…` until the report lands; clearing the body closes the tab.
6. e2e: drop a bench-swept bracket (plate with a bore) on the no-modeller page, read the report off the tab, shut and reopen it without a second survey, forget the body.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Placement: the editor group, as a document tab beside the script and its values file.**

Why: the report is per-body, not per-run. It arrives once per drop and is read while many runs go by; the bottom panel is redrawn by every run (stdout, stderr, problems, files all come off the scene) and sized for a run's output, so a 129-589 line document there would either be a strip to read through a letterbox or would need the panel resized every time - and it would have to be special-cased to survive each scene. The editor group already holds documents that outlive runs (the values file) and closable ones (sheets, PR #21's pattern), scrolls a `<pre>` at full height, and keeps the view on screen by the app's own rule. The cost: reading the report and the script at the same instant means switching tabs, as it does for the values file - there is no split editor.

What the panel would have cost: a fifth tab whose contents are not from the scene and must be preserved across `received()`, a reading height of ~150 px for hundreds of lines, and the problems badge/collapse semantics that do not fit a document.

**How it runs.** `web/src/worker.ts` gains a `survey` request and a second queue slot; its Python entry is one line composing `bench.mesh_from_stl`, `bench.survey`, `bench.report` - the same reader the run puts the body through to bind `reference`, and no modeller anywhere. The survey is asked once per drop (a real export takes seconds to measure) and kept for as long as the body is; the run goes first so the view follows the typing. Outside the watchdog and Stop: a survey is bounded by its triangles.

**Verified:** `uv run tools/check.py` green in an equipped worktree: 747 Python passed twice (+1 pre-existing skip), 169 component tests, 69 e2e (66 + 3 new). `src/bench` untouched.

**Limits not solved:** (1) no real hundreds-of-lines STL is in the repo, so the e2e reads a 59-line bracket and asserts the tab scrolls (`overflow-y: auto`) rather than reading a 589-line handle. (2) No component tests were added: the new code is page wiring (main.ts, index.html, bridge, worker), not a component; the values tab is a `<pre>` for the same reason. (3) A file the reader refuses (ASCII STL) fails the run - which already says why in Problems - and the chip reads `no survey`; the report tab does not open. (4) The reference and its report are held in memory only, as the reference already was: a reload forgets both.

Merged as cd7b28f (PR #25, squashed). Branched from 729b9ae, pushed without incident. Gate: 747 Python x2 (+1 pre-existing skip), 169 component, 69 e2e (66 baseline + 3 new). Criterion #4 verified by inspection as well as by claim - the diff touches no file under src/bench.

Placement: the editor group, as a closable document tab named for the dropped file, beside the script and its values. The reasoning is worth keeping: the report is per-body, not per-run - it arrives once per drop and is read across many runs - whereas the bottom panel is redrawn by every scene and sized for a run's output, so a 129-589 line document there would be read through a ~150 px letterbox and would need special-casing to survive each run. The editor group already holds documents that outlive runs (the values file) and closable ones (sheets). Cost of the choice: reading report and script at the same instant means switching tabs, as the values file does; there is no split editor.

How it hangs together: a `survey` request type in worker.ts with its own queue slot, so a keystroke's run supersedes the previous run rather than the survey, and the run goes first so the view follows typing. Surveys sit outside the watchdog and the Stop/busy state, being bounded by triangle count rather than able to loop. On drop the app runs then surveys once; the chip gains a survey button reading 'measuring...' until it lands and reopening the tab afterwards without measuring again; clearing the body closes the tab.

CAVEAT ON CRITERION #2, recorded rather than smoothed over. The criterion asks for readability at the length real parts produce - hundreds of lines. The e2e proves scrolling on a 59-line report from a bench-swept bracket, plus `overflow-y: auto` and a visually checked screenshot; it does not read a 589-line handle report, because no large STL is committed to the repo and adding one to a test fixture was not worth the weight. So #2 is evidenced by scroll behaviour and a visual check, not by a hundreds-of-lines report under test. The agent disclosed this rather than letting the tick stand unqualified.

Other limits it named: long report lines overflow horizontally (white-space: pre, scrollable); no component tests were added because the new code is page wiring rather than a Lit component, so that count stays 169; an ASCII STL the reader refuses fails the run with the reader's reason in Problems and the chip then reads 'no survey'; reference and report live in memory only, so a reload forgets both, as the reference already did; and nothing in the status bar reports a survey in progress - only the chip does.

One README nuance: the line saying the worker's Python 'lives in worker.py, not as a string in TS' is slightly bent by the one-line survey entry in worker.ts. Moving it into bench/worker.py would have violated criterion #4, and the line carries no logic of its own; a comment in worker.ts says so.
<!-- SECTION:NOTES:END -->
