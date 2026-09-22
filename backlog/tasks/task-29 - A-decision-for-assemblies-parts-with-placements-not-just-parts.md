---
id: task-29
title: 'A decision for assemblies: parts with placements, not just parts'
status: Done
assignee: []
created_date: '2026-09-22 22:41'
updated_date: '2026-09-22 03:02'
labels:
  - feature
milestone: Assemblies & Motion
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Write the decision document only. No code. This is design-heavy and reaches the scene contract, the stage, the viewer and the checks, so it wants the decision-4 treatment first.

**The evidence.** task-27 built one hinge stack of twelve bodies and every awkward thing about it came from the same absence. bench has `part()` and a stage that lays parts out for manufacture; it has no way to say how parts sit together. So the agent transformed twelve bodies by hand to pose them, then fused the result into a separate `stack-posed` body it had to label "a view and not a print" - because the stage lays bodies in a row, the thing a maker actually wants to look at had to be built as a thirteenth fake body beside the real ones. It also drove `min_gap` pairwise over every pair of the twelve at eleven poses as hand-written calls.

**What the document has to answer.** Where a placement lives (derived from parameters as a function, or held as data); whether an assembly is a scene concept or a part concept; how the stage's manufacture layout stays separate from it, since a part prints flat and sits posed and both are true; what the viewer draws and how that respects the rule that Python owns all geometry and TypeScript only draws; and how a check addresses an assembly rather than a list of bodies.

Worth arguing rather than assuming: whether a posed assembly is ever exported, or is strictly a view. task-27's `stack-posed` fudge exists because that question had no answer.

Blocks the contact and motion tasks: both need a way to name the parts and their relative placement before they can say anything.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The document says where a placement lives and why, and whether it is derived or held
- [x] #2 Manufacture layout and posed assembly are separable, so a part can print flat and sit posed without a fake body standing in
- [x] #3 It says how a check addresses an assembly instead of a hand-written list of pairs
- [x] #4 Nothing in it requires geometry computed in TypeScript
- [x] #5 What it deliberately leaves out of step one is named, as decision-3 and decision-4 both do
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
decision-6 merged (PR #37): backlog/decisions/decision-6 - An-assembly-is-a-scene-not-a-part.md. Its actual implementation (Assembly.posed, check_clearance_within, the viewer's branch) was filed separately as task-36, since this task was decision-document-only per its own instructions - see task-36 and task-34's notes for why that distinction mattered.
<!-- SECTION:NOTES:END -->
