---
id: task-23
title: A concave round nearly all the way around is not a rod
status: Done
assignee: []
created_date: '2026-09-22 03:43'
updated_date: '2026-09-22 22:04'
labels:
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Noticed while reading report() against the real systainer handle during task-22, and deliberately left for its own task rather than folded into that one.

The handle has two 345-degree concave rounds at r 2 - a 4 mm bore opened along one side by a slot. The report offers them as "a rod or a bar if the surface goes on round, a fillet or an eased edge if it rounds a corner". A concave surface has material OUTSIDE it, so it is a bore or a slot; it is not a rod, and at 345 degrees it is not an eased edge either. Both halves of the candidate are wrong for this surface.

The survey already records what is needed to tell the difference: a round carries whether it is concave or convex, and its turn. A convex surface that goes nearly all the way round is a rod; a concave one is a bore that something has opened into. A bore's candidate is `hole(...)`, which the report already writes for full circles - the gap is that a nearly-full concave turn falls through to the partial-round wording instead.

This is the failure mode task-14 exists to avoid: not a terse phrasing, but a candidate a maker would act on and find wrong. It is report-side; the survey measured the surface correctly.

Worth checking while in there: what the report says about a concave partial round in the middle of the range - say 180 degrees - where neither "bore" nor "fillet" is obviously right, and whether saying less is better than choosing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A concave round that turns nearly all the way around is not offered as a rod or a bar
- [x] #2 A convex round of the same turn still reads as a rod or a bar
- [x] #3 Where neither reading is warranted the report says less rather than choosing one
- [x] #4 Nothing is claimed that the survey did not measure, and no intent is inferred
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch `concave-not-a-rod` from origin/main (f0b25fa), PR #31 against main, not merged.

Fix is in `_partial_candidate` (src/bench/report.py), the wording used for a partial round lying off the Z axis. It now branches on `Round.concave`:
- convex: unchanged - "a rod or a bar if the surface goes on round, a fillet or an eased edge if it rounds a corner".
- concave, turn >= `_BORE_TURN` (270 degrees, missing arc <= 90 degrees): "N degrees of a bore of diameter D lying along AXIS, missing G degrees - hole(...) with a slot or a wall opened into it along the missing arc; material is outside it, so it is never a rod or a bar".
- concave, turn <= `_FILLET_TURN` (180 degrees): "N degrees of a concave cylinder of diameter D lying along AXIS - a fillet or an eased edge rounding a corner; material is outside it, so it is never a rod or a bar" (a legitimate reading - the survey's own `Round` docstring calls an inside fillet concave).
- concave, 180 < turn < 270 (missing arc 90-180 degrees): "no candidate: ... too much arc to call a fillet or an eased edge and not little enough missing to be sure it is a bore something has opened into; the measurement above is all this is" - criterion #3, said rather than guessed.

The same "or a bent rod" bug existed in `_round_run_lines` (a run of touching partial rounds) and is fixed the same way: a concave run never offers the rod reading.

Thresholds argued from data, not chosen for effect: `_BORE_TURN` = 270 degrees because the handle's own two rounds measure 345, missing only 15 - clearly a circle short a narrow slot; `_FILLET_TURN` = 180 degrees (a half turn) reuses the figure the axis-along-Z corner wording already treats as the far end of a rounded profile ("a half turn is the end of a slot()"). The middle (missing arc 90-180 degrees) has no clean argument either way, so nothing is claimed there.

Real handle (obj_6, 7,750 triangles), before -> after for both 345-degree concave r 2 rounds:
before: "candidate: 345 degrees of a cylinder of diameter 4.000 lying along (0.707, -0.707, 0.000) - a rod or a bar if the surface goes on round, a fillet or an eased edge if it rounds a corner"
after: "candidate: 345 degrees of a bore of diameter 4.000 lying along (0.707, -0.707, 0.000), missing 15 degrees - hole(...) with a slot or a wall opened into it along the missing arc; material is outside it, so it is never a rod or a bar"

Tried and rejected: offering the bore-opened wording at any concave turn above 180 (no gap threshold) was rejected because a real 180-degree concave round on the handle (a shallow lip fillet) would then wrongly read as "a bore something opened into" when it is just as plausibly a fillet cut in half; a single cutover point (no middle band) was rejected for the same reason the task named 180 degrees explicitly as ambiguous - collapsing the two questions (how much arc for a fillet, how little gap for a bore) into one number cannot be defended on the handle's own data, so they are kept as two thresholds with a silent band between.

Existing test updated: `test_a_partial_round_about_z_is_a_corner_and_about_x_a_fillet` (renamed to `..._a_rod_or_a_fillet`) built its "systainer grip" fixture as `concave=True` while asserting the rod-or-bar wording, which only makes sense for a convex surface - the fixture was wrong for what it claimed to test, so it is now `concave=False`. Three new tests added for the concave cases (never a rod, nearly-full is a bore, mid-range gets no candidate).

Gate (fresh worktree, npm ci + generate first): 776 Python passed twice (773 on main + 3 new, +1 pre-existing skip), 169 component, 73 e2e, ALL CHECKS PASSED. No count came out lower than baseline.

Known limit, not solved: at exactly the 180-degree boundary, two real pieces on the handle both display as "180 degrees" (fixed-place rounding) but land on opposite sides of `_FILLET_TURN` because their actual measured turn differs by a sub-degree amount - one gets "no candidate", the other gets the fillet reading. This is a display-precision artifact at a hard cutoff, not something this fix introduces or fixes; flagging it because it is visible on this real part.

Note: origin/main moved to c784881 (3 commits ahead) partway through this work; branched and gated against the earlier f0b25fa and did not rebase, per instructions to wait to be asked.

Rebased onto origin/main at 26c707a per coordinator request (main had moved to include task-27's fulcrum hinge example, 4 commits past the f0b25fa this branch was cut from). `git rebase origin/main` was clean - no conflicts, as expected since this branch only touches src/bench/report.py and tests/unit/test_report.py. New local commit db449bf5aa7e288d8791436b8f93504ad944a523, tree 5f157115323eccf5832d2ca9e564c37a2f6dcaaa.

Checked the specific risk before trusting the rebase: does anything in tests/adapter or tests/functional (the layers that exercise examples, including the new fulcrum_hinge.py) assert on bench.report's output? Searched the whole repo at origin/main for `bench.report` / `from .report` / `import report` - the only call sites are tests/unit/test_report.py, src/bench/__init__.py's export, and web/src/worker.ts (the app's live survey feature, not exercised by the adapter/functional example tests). Neither test_examples_measured.py nor test_examples.py imports or calls report() anywhere, for this example or any other - confirmed by reading the diff of 2171fae and grepping, not assumed. So the wording change in this PR cannot have moved anything in those layers, and the gate result bears that out: the Python count landed exactly at 781 + 3 with nothing unexpected shifting.

Re-ran the full gate on the rebased tree, npm ci --prefix web && npm --prefix web run generate first (bundle-py picked up 9 examples, confirming the hinge example was included): 784 Python passed twice (781 on the new main + this PR's 3, +1 pre-existing skip), 169 component, 73 e2e, ALL CHECKS PASSED - matches the coordinator's expected 784/169/73 exactly, nothing lower than baseline.

`git push` was refused by the permission system on this rebased (force) push. Per instruction, stopped rather than working around it. Local commit: db449bf5aa7e288d8791436b8f93504ad944a523, tree: 5f157115323eccf5832d2ca9e564c37a2f6dcaaa - for the coordinator to compare against what a merge would produce. PR #31's remote branch still points at the pre-rebase commit (62b0485) until the coordinator lands this some other way.

Merged as 012ecdd (PR #31, squashed). Gate on the rebased tree: 784 Python passed twice (781 baseline + 3 new, +1 pre-existing skip), 169 component, 73 e2e. main's tree is exactly the gated 5f157115323eccf5832d2ca9e564c37a2f6dcaaa.

How it landed: the branch was based on f0b25fa and first gated at 776 Python, predating task-27's hinge example which added 8 non-e2e tests. After rebasing onto 26c707a the counts matched prediction exactly. The push of the rebased branch was refused by permissions and was NOT worked around - the agent stopped and reported its SHA and tree hash as asked. Because the rebase was clean and added no further commit, a squash of the stale branch produced the identical tree (verified: squash-of-origin and the gated tree are both 5f15711), so the PR was merged as it stood with no force-push and no cherry-pick. That is the fifth PR in this repo to land by tree comparison rather than by routing around a permission decision.

The fix: `_partial_candidate` now branches on Round.concave instead of using one sentence for both. Convex is unchanged. Concave at or above 270 degrees (missing arc 90 or less) reads as a bore something has opened into, naming the missing arc and saying outright that material is outside it so it is never a rod or a bar. Concave at or below 180 degrees keeps the fillet-or-eased-edge reading, which Round's own docstring licenses ('an inside fillet' is concave). The same bug was found in a SECOND place the task did not name - `_round_run_lines`, where a run of touching concave pieces was offered as 'or a bent rod' - and got the same treatment.

Criterion #3 is the part worth keeping. Between 180 and 270 degrees the report refuses to answer: 'no candidate: ... too much arc to call a fillet or an eased edge and not little enough missing to be sure it is a bore something has opened into; the measurement above is all this is'. The agent tried collapsing this to a single cutover so there would be no silent middle band, and rejected it on the reasoning that one number cannot defensibly answer both 'how much arc still reads as a fillet' and 'how little gap still reads as a bore'. Declining to guess is the right answer and is now the printed one.

Before/after on the real handle (obj_6), both 345-degree concave r 2 rounds: was 'a rod or a bar if the surface goes on round, a fillet or an eased edge if it rounds a corner'; now '345 degrees of a bore of diameter 4.000 lying along (0.707, -0.707, 0.000), missing 15 degrees - hole(...) with a slot or a wall opened into it along the missing arc; material is outside it, so it is never a rod or a bar'.

A test fixture was fixed rather than an assertion weakened: test_a_partial_round_about_z_is_a_corner_and_about_x_a_fillet built its 'systainer grip' with concave=True while asserting rod-or-bar wording, which is only valid for a convex surface - so it had been testing a contradiction. Fixture corrected to concave=False and the test renamed.

The rebase risk was confirmed rather than assumed, as asked: every call site of report in the repo was traced (only tests/unit/test_report.py, the __init__ export, and web/src/worker.ts), and the adapter and functional layers were grepped directly - neither imports or calls report() for the hinge example or any other. Report wording cannot leak into those layers.

LIMIT DISCLOSED, not fixed: at exactly the 180-degree boundary two real pieces on the handle both display as '180 degrees' (rounded for print) but sit on opposite sides of _FILLET_TURN because their true turns differ by a sub-degree amount, so one prints the fillet reading and its neighbour prints 'no candidate'. Adjacent readings disagreeing looks like a bug to a reader even though each is correct. Not introduced by this change. This is the third instance in this codebase of a hard threshold sitting exactly where real data falls - task-20 was the survey's default heights landing on a part's own plateaus, and task-22's sliver rule was the same shape - which is a pattern worth naming rather than patching case by case.
<!-- SECTION:NOTES:END -->
