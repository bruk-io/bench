---
id: task-35
title: 'Clearance holds through a motion, not just at poses somebody picked'
status: Done
assignee: []
created_date: '2026-09-22 22:42'
updated_date: '2026-09-22 03:02'
labels:
  - feature
milestone: Assemblies & Motion
dependencies:
  - task-36
  - task-34
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
task-27 checked its hinge by calling `min_gap` on every pair of twelve bodies at eleven hand-picked poses - closed, three of the patent's positions, open, a handover at maximum travel, and knob extremes. It came back clear, and that is worth something, but eleven samples of a continuous motion is eleven samples: the pose where two rings actually foul each other may sit between two of them.

This is the honest substitute for kinematics, and it stays inside what bench is: pure geometry. Given an assembly and a parameter range, either sample it densely enough to mean something or sweep the volume each part occupies across the range and check those. It cannot say anything about force, friction or whether a mechanism will bind - task-27's interlock question stays unanswerable here, and this task must not pretend otherwise.

**Depends on task-29** (an assembly to move - there is nothing to sweep without relative placement) **and on task-34** (a moving assembly is full of intentional contact; without contact declared, every bearing face would report a failure at every step and drown the real finding).

The reporting matters as much as the check. "Clear at 11 poses" and "clear throughout 0 to 1" are different claims, and a swept check that samples must say which it made and at what spacing, rather than implying continuity it did not prove.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A clearance check takes a parameter range and reports on the whole of it, not one pose at a time
- [x] #2 A pair that fouls only between two hand-picked poses is found
- [x] #3 The result says whether it swept or sampled, and at what spacing, so the claim is not stronger than the evidence
- [x] #4 Declared contacts are honoured throughout the motion rather than failing at every step
- [x] #5 Nothing claims anything about force, friction or binding - only about whether the geometry interferes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Sample, do not sweep. Four reasons, all verified against the code:

1. A union of a part's solid at N poses is sampling with the samples glued together, and it loses which pose fouled.
2. `hull` is not a conservative over-approximation of a rotation: a point travels an arc and the hull of the two end positions contains the chord, not the arc's outward bulge. A hull sweep can pass a pair that fouls mid-travel - exactly criterion #2's failure.
3. There is no 3D dilation to fix that. `offset` is a flat/kerf modifier (ops.py) and `Kernel` is `mesh`/`volume`/`min_gap` only - no Minkowski, no inflate.
4. Decisive: in fulcrum_hinge nearly every part moves, and parts that move together (link-1 and shaft-2, a declared seat) have swept volumes that interpenetrate hugely while the pair is fine at every instant. Swept-volume clearance is only meaningful moving-against-static; in a four-axis linkage it fails almost every pair, which makes criterion #4 unsatisfiable rather than merely awkward.

Shape:
- `check_clearance_through(at, least, *, over=(0.0, 1.0), samples, contacts=())` in `script.py` beside `check_clearance_within`. `at` is `Callable[[float], Assembly]` - the script's own "give me the assembly posed at t".
- `contacts=` does both jobs (exclude from the clearance walk AND run `contact_between` at every sample), deliberately unlike `check_clearance_within`'s `exclude`: a script never sees the sampled poses, so it cannot call `check_contact` itself, and `exclude` alone would leave the seats unchecked at all but one pose (criterion #4).
- Returns a frozen `Sampled` record (checks.py, beside `Violation`): least, over, samples, spacing, findings, measured. Its sentence says *sampled*, never swept, gives N and spacing, and carries the force/friction/binding disclaimer (criteria #3, #5). The example prints it.
- One finding per offending pair (the first sample that fails), message naming both part labels and the parameter value and sample index. Refs are empty by construction - `views._label_of` matches by identity and a posed body from sample t is not a shown part - so the labels go in the message text, documented.
- No kernel: one UNCHECKED finding and `measured=False`, without building any pose, so the kernel-free layers stay fast.

Runtime, measured in the shipped stack (Pyodide + Manifold under node): one full fulcrum run is ~1.0 s, of which the 66 `min_gap` calls plus 4 contacts are ~0.9 s and everything else 0.15 s. So each extra sample costs ~0.9 s. The example gets a `samples` knob so the adapter layer's pose cases can dial it down.

Work: the check, the record, fulcrum_hinge refactored so the pose is a function of deployment, functional tests (reporting, contacts honoured, unchecked), an adapter test with the real kernel for criterion #2 - a pair clear at both hand-picked ends that fouls in the middle.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dependency corrected from task-29+task-34 to task-36+task-34. task-29 is a decision DOCUMENT only (status proposed) - it does not provide an actual posed Assembly to sweep. task-36 is the filed implementation of decision-6 (Assembly.posed, check_clearance_within, the viewer's drawing branch); this task needs task-36's code, not task-29's document alone. Discovered while executing task-34, which was originally briefed on the same wrong assumption.

Implemented on branch task-35-motion-sampling, PR https://github.com/bruk-io/bench/pull/41 (left for the main session to review and merge; task left In Progress deliberately).

Sampled rather than swept. Decisive reason: a linkage sweeps through itself - shaft-2 is keyed to link-1 and they turn together, so their swept volumes overlap entirely while the pair never meets at any instant, which would make criterion #4 unsatisfiable. Also: a hull of two poses holds the chord a point travels, not the arc, so it is not even conservative; there is no 3D dilation in mesh/volume/min_gap to build a conservative sweep with; and a union of poses is sampling that has lost which pose fouled.

Shipped: `check_clearance_through(at, least, over=, samples=, contacts=)` in script.py, `Sampled`/`sampling` in checks.py, `unchecked()` made public so the edge can say 'not measured' in the same words. `contacts=` both excludes from the clearance walk and runs contact_between at every pose, deliberately more than check_clearance_within's `exclude`. fulcrum_hinge poses through one `stacked(deployment)` and comes back clear at 21 deployments, 0.05 apart.

Known limitation, documented rather than worked around: findings from sampled poses carry no refs (views._label_of matches by identity and a sampled body is no shown part), so both labels and the parameter value are in the message text.

Measured: ~0.9 s per pose in the shipped stack; the adapter module went 7.7 s to 34 s, with the five POSES cases dialled to samples=2. Full gate green (844 x2, 73 e2e).
<!-- SECTION:NOTES:END -->
