---
id: task-42
title: >-
  Build decision-7's pick: click a flat, click a corner, get a readout - not yet
  a written [reference]
status: Done
assignee: []
created_date: '2026-09-22 03:25'
updated_date: '2026-09-22 04:09'
labels:
  - feature
  - web
milestone: Reverse Engineering
dependencies:
  - task-37
  - task-40
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Roadmap item 3 of the reverse-engineering line of work (consulted with Fable - see task-40's notes for the roadmap in full). decision-7 (task-37, `backlog/decisions/decision-7 - A-pick-writes-numbers-never-a-surveys-own-indexing.md`) designed a pick that resolves to numbers at the moment of the click, snapping to a named form only within tolerance of a survey extremum. task-40 built the click detection this needs (a mode-gated backdrop raycast, resolving a click to a detected flat) but only logs the result to the console and a button tooltip.

Fable's assessment, worth holding to: "click a face -> number" is marginal on its own; it is only worth finishing as decision-7's own pick, with a real readout (normal, centre, area; the distance between two picked flats, which is how a maker actually measures a wall) - not as a "copy as bench code" generator. task-14.3 and decision-7 both already hold the house position that drafting a script from measurements is a person's job, or a collaborating model's, never something bench infers automatically. This task builds the pick and the readout; it does not write `[reference]` from a click, and does not draft any code.

Read decision-7 in full before starting. Its own open questions ("still the owner's call") - whether a pick writes immediately or waits for confirmation, what the snap tolerance should be, what "place this" mode looks like with nothing dropped - are this task's to answer, not to leave open a second time.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A maker can pick a flat (for up) and a corner (for origin) in the view and see the resolved numbers, snapped to a named word within tolerance of a survey extremum or written as a triple otherwise, per decision-7
- [x] #2 A long-dormant question from decision-7 is answered rather than left open: whether the resolved numbers are written to [reference] immediately or only after confirmation
- [x] #3 along stays typed, per decision-7's own explicit scope - no edge-pick is designed or built here
- [x] #4 Nothing here drafts bench code from a measurement - the output is numbers a maker reads or (per the criterion above) numbers written to [reference], never generated script text
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Answers to decision-7's three open questions, then the build.

1. **Immediate or confirm? Confirm** - and from the code, not taste. `main.ts:matchedReference()` applies a `[reference]` table the moment `table["file"]` is the dropped file's name; that table then feeds every run, every survey and every detection through `worker._placed` -> `placement()`, which raises `ValueError` on a missing `origin`/`up`/`along`. So an immediate per-field write breaks the app until all three exist, and the mesh a pick is measured against moves the moment the table lands. The pick therefore fills a draft, and one explicit "write [reference]" commits all three at once (with `file`), then re-runs so the chip's "placed" is honest.
2. **"place this" with nothing dropped:** the question cannot arise - the reference chip is `hidden` until a body is dropped, and the pick panel lives inside it. The mode itself is the existing "detect faces" toggle (task-40), which is already the only thing that makes the backdrop pickable; no second mode is invented.
3. **Tolerance:** `ROUND` is kept (it is `bench.survey.ROUND` = 0.01 mm, not `bench.topology`'s - decision-7 misnames it), but its job changes: 0.01 mm is ~1/17 of a pixel at normal framing, so as a *mouse* tolerance the snap would be dead code. The maker's own click decides word vs triple; `ROUND` only certifies that the chosen point is exactly a named point. The readout shows the raw hit, the nearest vertex of the hit triangle, and the measured distance to low/high/centre; assigning the nearest vertex on an axis-aligned box lands on `Extent.low` itself, so the word is written for the right reason (float noise from the STL round-trip), not from an invented figure (decision-5).

Build:
- `src/bench/placement.py`: public `named_origins(mesh)` - the very points `_origin` resolves `"low"`/`"high"`/`"centre"` to, so a snap can never disagree with the resolver.
- `src/bench/worker.py`: `detected()` also reports those origins and the snap tolerance.
- `web/src/pick.ts` (new, pure): the snap rule, the readout's distances, and reading/writing a field's text as a word or a triple.
- `web/src/viewer3d.ts`: `onDetectPick` hands back the hit point in the backdrop's own coordinates and the nearest vertex of the hit face, not only the flat index.
- `web/src/main.ts` + `web/index.html`: the pick panel - readout (normal/centre/area, hit, distance from the previous pick), editable `origin`/`up`/`along`, and one "write [reference]" that commits and re-runs. Refused, with the reason, while a placement is already applied (the hit would be in the placed frame); a "clear placement" beside it.
- `along` stays typed. Nothing generates code.
- Tests: the snap (exactly at `Extent.low` -> `"low"`; `low + 2*ROUND` -> a triple), the shipped origins agreeing with `placement()`'s own resolution, a noisy triple round-tripping through `toml`/`fromToml`, and task-40's AC #3 (detection off -> backdrop unpickable, panel gone).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built. decision-7's three open questions are answered in the plan above and in the code's own comments.

**Immediate vs confirm: confirm, and the code decides it.** Verified empirically before building anything: `bench.worker._placed(mesh, '{"file": "x.stl", "origin": "low"}')` raises `ValueError: reference table has no 'up'`. Since `main.ts:matchedReference()` applies a table the moment its `file` names the dropped body, and that table then feeds every run, survey and detection, a write-per-pick would break the app between the first pick and the last - and would move the mesh the second pick is measured against. `[values]` has no such feedback loop. So the pick fills a draft and one "write [reference]" commits all three, then re-runs and re-measures.

**Tolerance: `ROUND` kept, its job changed.** It is `bench.survey.ROUND` = 0.01 mm (decision-7 calls it `bench.topology.ROUND`; that module has no such constant). 0.01 mm is a small fraction of a pixel at any framing, so as a mouse tolerance the snap would never fire. The maker's own click now decides word vs triple - the panel offers the hit point *and* the nearest corner of the face it met - and `ROUND` only certifies that the chosen point *is* the named point. No new figure invented (decision-5).

**Verified live** in a real browser (headless chromium, a 60x40x3 bracket dropped over an 8 mm plate so the backdrop is clickable): a mid-face click reads `flat 1 · 2372.3 mm², normal (0,0,1), centre (30.175, 20.000, 3.000), hit (2.853, 26.163, 3.000), corner (12.7019, 18.0716, 3.0000), corner from low 22.292 mm · high 52.134 mm · centre 17.470 mm`; a second pick adds `from the pick before: 6.870 mm`; a click near the body's own corner reads `corner from low 0.000 mm` and "origin = corner" writes `low`, saying why. A partial commit is refused naming `along`; the whole one writes `[reference]` into the values file, the chip says `bracket.stl · placed`, and the panel then says `reading the placed frame` with its write disabled and `clear placement` offered.

**Known limitation, not shipped around:** `plane(origin, up, along)` raises when `along` is parallel to `up`, so picking a +Z-ish face for `up` and typing `+Z` for `along` fails at the run with the reader's own message rather than in the panel. The panel does not pre-validate; `placement()` remains the one reader that judges a value.
<!-- SECTION:NOTES:END -->
