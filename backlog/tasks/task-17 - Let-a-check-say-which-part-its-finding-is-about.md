---
id: task-17
title: Let a check say which part its finding is about
status: Done
assignee:
  - claude
created_date: '2026-09-22 19:05'
updated_date: '2026-09-22 01:30'
labels:
  - bench
  - scene
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A check reports the face it measured in the **solid's** own namespace: `check_overhangs` on the tote answers `socket-1`. The scene's ref table, and anything reading it, holds the part-qualified path - `tote/socket-1`. They never match, so nothing downstream can line a finding up with the geometry it is about.

This surfaced in the workbench shell, where the refs tree marks the rows a check reported: the marking logic is right and tested, and with the shipped examples nothing is ever marked, because the two namespaces never meet. It was left unmet in task-15.2 rather than papered over, since the page cannot bridge it - a `ViolationView` carries the check, its message, a severity, refs and a line, and never says which part the finding was about.

Matching on the last path segment is not the fix: it marks the wrong row the first time two parts share a face name, which they routinely do - every panel of the cabinet has a `bottom`.

What closes it is a finding that names what the rest of the run names. That is a change in `bench` rather than in `web/`: either a check reports the part-qualified ref, or a violation carries the part alongside the refs it measured. Both touch the closed scene contract, so `web/src/scene.ts` moves with it.</description>
<parameter name="acceptanceCriteriaAdd">["A finding's refs name the same thing the scene's ref table names, so a reader can line the two up without guessing", "Two parts sharing a face name do not get each other's findings", "The scene contract and its TypeScript mirror agree, and the contract test proves it", "The refs tree marks the row a check reported, with the e2e check that was withdrawn restored rather than loosened"]
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A finding's refs name the same thing the scene's ref table names, so a reader can line the two up without guessing
- [x] #2 Two parts sharing a face name do not get each other's findings
- [x] #3 The scene contract and its TypeScript mirror agree, and the contract test proves it
- [x] #4 The refs tree marks the row a check reported, with the e2e check that was withdrawn restored rather than loosened
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Plan

Verified first: every example runs its checks on a bare solid *before* `part(...)` exists (`systainer_tote.py:256-260`, `enclosure_lid.py:92-104`, `hinge.py:111-125`), so "the check reports a part-qualified ref" cannot be done in `checks.py` without rewriting every script. `checks.py` stays pure.

1. `views.py` gains a `Finding` NamedTuple: the `Violation` plus the shapes the check was handed (`subjects`). `scene()` takes `findings` instead of `violations`.
2. `views._qualified(finding, parts)` matches each subject against `part.shape` **by identity** (`is`) and prefixes that part's label onto the violation's refs - the same rule `_mesh_view` already applies to a kernel's refs. No match: refs left as they are, never guessed from the last segment. A finding with no refs (fits, clearance) that is ERROR/WARNING names each subject that became a part - `check_fits(tub)` answers `tote`; UNCHECKED names nothing because nothing measured anything.
3. `script.py`: `_recorded` takes the subjects; `_Recorder.findings`; the four closures pass what they measured (`shape`, `(a, b)`, `solid`).
4. `ViolationView` and `scene.ts` do **not** change: refs are qualified at the edge rather than the record widened, so criterion #3 is met by the existing contract test and fixture.
5. Tests: functional (`test_script_checks.py`: fits names its part, an intermediate names nothing, unchecked names nothing; `test_views.py`: two parts sharing `top` keep their own finding), adapter (`test_examples_measured.py`: the collar's round-bore overhang finding is a ref the scene's own table holds), e2e: restore the withdrawn tree-flag assertion in `test_a_failed_check_is_reported_and_its_line_is_marked` and delete the withdrawal comment.
6. README `script.py` paragraph says where refs are qualified. Gate: `uv run tools/check.py` in full plus the three npm scripts.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## What changed, and why this shape

Every example checks a bare solid *before* `part(...)` exists, so a check cannot report a part-qualified ref itself and `checks.py` stays pure. Instead the run keeps what each check was handed: `script._recorded` takes the subjects, `_Recorder.findings` holds `views.Finding(violation, subjects)`, and `views.scene(findings=...)` qualifies each finding's refs under the part whose `shape` **is** the subject - identity, the same rule `_mesh_view` applies to a kernel's refs. No match: refs stay bare. No refs (fits, clearance): the finding names each subject that became a part - `check_fits(tub)` answers `tote`, a clearance between two parts names both. UNCHECKED names nothing: the tree's flag is drawn in `--danger` as "a check reported this", and an unmeasured question is not that.

`ViolationView` did **not** change - refs are qualified at the edge rather than the record widened - so `scene.ts` and `scene-fixture.json` are untouched. The task's assumption that both options touch the contract was wrong for this one.

## Checked rather than assumed

- Real kernel (Pyodide + Manifold under node): the enclosure at wall=1.2 reports exactly one finding, `wall` on `box/side-1`, nothing on the lid. The restored e2e assertion rests on that: the `box` row carries a `.flag`, the `lid` row exists and carries none.
- Adapter: the collar's round-bore overhang finding names refs under `collar/` that the scene's own ref table holds.
- Functional: fits names its part; a blank checked then moved names nothing; two cuboids equal by value are two parts and only the checked one is named; a wall finding on `top` lands on `b/top`, not `a/top`; unchecked findings have empty refs.
- Gate `uv run tools/check.py` in full: ALL CHECKS PASSED (690 x2, e2e 59). `npm run typecheck`, `lint`, `test` (148) green after `npm ci` + `npm run generate` in the worktree - a fresh worktree has neither, and without them the gate skips the web steps, the kernel adapter tests and e2e while still saying it passed.

## Honest limits on criterion #1

`fits` and `clearance_between` build violations with no face refs at all; for them the only thing to qualify is the whole body, which is what now happens (the part's own ref, which the table holds). Only `wall` and `overhangs` carry face refs and get `part/face`. A clearance between a part and an intermediate (the enclosure's `lip` against `box`) names only `box`.

PR: task-17-a-finding-names-its-part against main, not merged.
<!-- SECTION:NOTES:END -->
