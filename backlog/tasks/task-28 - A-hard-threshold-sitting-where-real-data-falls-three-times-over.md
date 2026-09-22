---
id: task-28
title: 'A hard threshold sitting where real data falls, three times over'
status: Done
assignee: []
created_date: '2026-09-22 22:05'
updated_date: '2026-09-22 13:26'
labels:
  - feature
milestone: Hardening
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Named because it has now happened three times in three different modules, each found by reading a real part rather than by a test, and each patched locally. The pattern is worth deciding about once rather than a fourth time by hand.

**task-20.** The survey's default section heights were multiples of h/6. Real parts are modelled at round numbers, so those heights landed exactly on the part's own vertex layers: a plane ran along a face instead of cutting through it and left zero-area runs - 36 on the systainer foot, 30 and 11 on the handle. Fixed by nudging a default height off any layer it lands within ROUND of.

**task-22 (and #24 before it).** The sliver rule keyed on a band's share of the surface, under 1% being "one place, not a wall". The base plate's four socket floors are 44.8 mm2 at 0.500 mm - a real thin floor a maker must know about - and fell under that share, so a genuine measurement was dismissed as a tessellation artefact. Fixed by making the rule absolute rather than proportional.

**task-23.** `_FILLET_TURN` is 180 degrees. Two real pieces on the handle both *display* as "180 degrees" after fixed-place rounding but sit on opposite sides of the cutoff because their true turns differ by a sub-degree amount, so one prints the fillet reading and its neighbour prints "no candidate". Each line is correct; adjacent lines disagreeing reads as a bug. Not fixed - disclosed.

**What the three have in common.** A threshold is chosen from what looks like a natural figure - a half turn, one percent, h/6 - and real parts are built on exactly those figures, because the people who drew them also liked round numbers. So the boundary does not fall in a sparse region of the data; it falls in the densest one. The survey's own tolerances (ROUND, SAME, PLACE, CHORD, TURN) are safer because they were argued from what the tessellation does, not from what reads nicely.

This task is to decide whether there is one answer worth having, rather than to apply a fix. Candidates, none obviously right: state a rule that a printed figure must carry enough precision to explain its own classification (task-23's artefact is invisible until you know the turns differ below the printed place); or require a threshold to be argued from a measured distribution, as task-22's _DRIFT was from the touching-pair radius histogram, rather than from a round number; or treat a reading within display precision of a boundary as a third state and say so, which is what task-23 already does between its two thresholds and what task-22 did by printing the reading beside the band area.

It is also worth asking whether this deserves a line in the report module's docstring or in README rather than code at all. The honest possibility is that the answer is a written rule for whoever adds the next threshold, and no change to any module.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The three existing cases are stated in one place with what they have in common, so the next person adding a threshold meets the pattern before repeating it
- [x] #2 Either a rule is written that a new threshold must satisfy, or it is argued that no general rule is worth having and why
- [x] #3 task-23's 180-degree artefact is either resolved or recorded as accepted with the reason
- [x] #4 No threshold is changed without an argument from a real part's measured distribution
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Wrote backlog/decisions/decision-5 - A-threshold-sits-exactly-where-real-data-falls.md, stating the three cases (task-20's h/6 heights, task-22/24's sliver share, task-23's _FILLET_TURN) and the rule: argue a threshold from a measured distribution, and where it decides real-vs-artefact rather than how a reading is shown, make it absolute over the printed unit rather than a share (LEAST/_TAIL is the working example already in the code). Confirmed LEAST is already absolute in report.py's _thinnest - task-22's fix - so no threshold changed there.

task-23's 180-degree boundary artefact was disclosed only in task-23's closed backlog notes, not in the code. Added a paragraph to _FILLET_TURN's docstring in src/bench/report.py recording it as accepted-with-reason (no alternative figure survived task-23's search; widening _deg's precision would move every degree reading in the report, out of scope here). Also added a module-docstring section in report.py pointing at decision-5 so the next threshold author actually meets the pattern in the code they are editing, not only in a decisions file nothing links to.

No threshold value changed - verified by git diff: every changed line in src/bench/report.py is prose inside a docstring, no numeric literal touched. Only new file is the decision doc.
<!-- SECTION:NOTES:END -->
