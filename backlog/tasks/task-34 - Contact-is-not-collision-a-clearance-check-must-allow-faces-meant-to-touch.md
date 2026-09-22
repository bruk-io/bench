---
id: task-34
title: 'Contact is not collision: a clearance check must allow faces meant to touch'
status: Done
assignee: []
created_date: '2026-09-22 22:42'
updated_date: '2026-09-22 19:19'
labels:
  - feature
milestone: Assemblies & Motion
dependencies:
  - task-29
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`min_gap` reads a coplanar pair as a clearance failure, and there is no way to say two faces are meant to be in contact. task-27 hit this twice - the shaft head against its ring, and the stop lug against its ring - and the only remedy available was to BURY the geometry in its neighbour so the faces were no longer coincident. That is a real shape being distorted to satisfy a check.

Every assembly has intentional contact: a head seats, a lug bears, a shoulder stops. Until a check can express that, it cries wolf on every one of them, and the fix is always to move geometry that was right.

**Depends on task-29** (the assemblies decision), because naming which pair touches is assembly-shaped: it needs a way to refer to two parts and the faces between them. A narrower version - an explicit per-pair allowance passed to the check - could be built before the decision lands, but it would likely be replaced by whatever the decision settles, so it is not worth doing twice.

Criterion #4 is the one to hold to. A contact must be DECLARED, never inferred from a zero reading: if the check treats any zero gap as intentional, a genuine collision that happens to touch exactly would pass silently, which is worse than the false alarm this task removes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A pair of faces declared to be in contact does not read as a clearance failure
- [x] #2 A pair that should be clear and is not still fails - the allowance is per-pair, never global
- [x] #3 task-27's buried shaft head is un-buried (drawn flat on its ring, not a fit short of it) and the check still passes via a declared contact; the stop lug's own millimetre is retained for printability (it prevents an overhang), not because any clearance check needed it
- [x] #4 A contact is always declared, never inferred from a zero or near-zero reading
- [x] #5 A declared contact that turns out to be an overlap rather than a touch is still reported
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. `checks.contact_between(a, b, *, kernel)` - a declared contact is CHECKED, not skipped: the passing rule becomes "these two do not interpenetrate" (shared volume zero) instead of "these two are `least` apart". Measured with `kernel.volume(Solid(Intersection(a, b)))` - `Intersection` is a `topology` node and `checks` already imports `topology`, so this needs no fourth `Kernel` method and no layer-graph change.
2. `script.check_contact(a, b)` injected beside `check_clearance`, recorded through `_recorded(..., (a, b))` so a finding names both parts.
3. `examples/fulcrum_hinge.py`: un-bury the shaft head (`y0 - fit` -> `y0`) and declare the four head/ring pairs with `check_contact`; the `combinations` loop skips exactly those four, and that skip IS the declaration. The lug stays buried - measurement shows un-burying it causes no clearance failure at all, only an overhang warning, so it was never this task's to free.
4. Tests: a declared contact passing where an undeclared pair fails; an undeclared pair still failing; a declared contact that is an overlap still reported; a declared pair that is merely apart (documented, not silently passed).
5. NOT built: `Assembly.posed` / `check_clearance_within` - that is task-29's scope and decision-6 has not shipped. `check_contact` is a different measurement, not the throwaway "per-pair allowance" task-34 warns against, so it survives decision-6 landing.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built `contact_between(a, b, kernel)` / `check_contact(a, b)` in src/bench/checks.py + script.py (PR #39): a declared pair gets this check *instead of* check_clearance, measuring shared volume (via the existing `Intersection` topology node, `kernel.volume` - no new Kernel method) rather than distance, since min_gap reads a touch and a collision as the same zero. `_SHARED_SLACK` (1e-6 mm3) is argued from measurement per decision-5's rule: an exact touch reads exactly 0.0 on the shipped kernel, the smallest overlap tried reads 0.0494 mm3, four orders of magnitude apart.

Rejected explicitly: a per-pair exclude/allowance list (decision-6's own stopgap - fails criterion #5 by construction, since skipping a pair means an overlap in that pair reports nothing) and inferring contact from a zero reading (the exact failure mode the task warns against).

Real finding, verified by measurement not assumed: task-27 buried geometry in TWO places, but only one (the shaft head against its ring) was actually a clearance-check workaround. The stop lug's millimetre-in-from-the-face was checked by un-burying it against the real kernel - it raises no clearance finding at all (lug and ring are one body; min_gap is never asked about a body and itself), only an overhang (the lug's outer arc loses what was under it and leans 90 degrees off the build direction). So the lug's bury is retained, for printability, and is not something `check_contact` needed to fix. Acceptance criterion #3 reworded above to reflect this rather than being ticked against a premise that measurement disproved.

Per-pair matching in fulcrum_hinge.py is by Python object identity (`id()`), not by label, because there is no assembly/label vocabulary a check can address yet - that is decision-6's implementation, not yet built (see new task for it). This is a real constraint, not a style preference.

Important discovery: decision-6 (task-29) is a decision DOCUMENT only, per its own task's instructions. `Assembly.posed` and `check_clearance_within`, which decision-6 proposes, were never implemented - task-29 being Done means the document exists, not that the code does. This was not tracked anywhere and blocked this task's original brief (which incorrectly assumed the code existed). See task-40, filed to close that gap - task-35 depends on task-40's code landing, not on task-29's document alone.

Correction: the follow-up task filed for decision-6's implementation is task-36, not task-40 as guessed in the note above.
<!-- SECTION:NOTES:END -->
