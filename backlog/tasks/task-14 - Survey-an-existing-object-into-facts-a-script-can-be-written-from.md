---
id: task-14
title: Survey an existing object into facts a script can be written from
status: Done
assignee: []
created_date: '2026-09-22 13:54'
updated_date: '2026-09-22 02:46'
labels:
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A maker who wants to model something that already exists - a downloaded model, a part off the shelf - currently has to measure it by hand and guess, and the guessing shows up as defects that only a kernel run catches later.

This gives bench a way to be handed an existing object and answer with its measurements, expressed in bench's own vocabulary, so that writing the script - by hand, or drafted by a model from the report - starts from facts rather than from recollection.

Two boundaries are deliberate. Images are out of scope: turning photographs into a mesh needs weight bench does not carry, and bench starts where a mesh starts. Writing the script is out of scope too: the answer reports what was measured and offers the vocabulary that fits it, and never guesses intent - it can say a bore is 4.5 mm across, it cannot know that this was asked for as a clearance hole at a named fit.

The value is the split. What can be measured is deterministic, testable and repeatable, and belongs in the package; what has to be interpreted is the reader's, or a model's, and belongs outside it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A maker can hand bench a mesh of an existing object and get back its measurements without a solid modeller present
- [x] #2 The answer is data, and rendering it for a reader is a separate step from producing it
- [x] #3 The report states what was measured in bench's own vocabulary, and says nothing it did not measure
- [x] #4 Intent is never inferred: no clearance, fit or nominal is claimed from a measured dimension
- [x] #5 No new runtime dependency is added to the package
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Closed after 14.1, 14.2 (#22) and 14.3 (#23, #24) landed, and specifically after the report was read against real CAD exports rather than hand-built fixtures.

That last step is why the parent stayed open an extra round, and it earned its keep. The reading of the Festool systainer STLs (front foot 2,988 triangles, main handle 7,750, base plate 17,272) was NOT clean - it found one correctness bug and two misleading behaviours, all fixed in #24:

1. A real thin floor was dismissed as a tessellation artefact. The base plate's thinnest reading, 0.500 mm under 44.8 mm2, is the four 3.8 x 3.8 mm socket floors - something a maker must know about - and the share-based sliver rule (<1% of surface) called it 'one place ... and not a wall'. The rule is now absolute: under 1 mm2 behind the reading is a sliver, 1 mm2 or more is 'a thin place of that area, not one of the walls above, and the number check_wall() reads first'.
2. The report claimed defects that did not exist. The survey's default heights are h/6 multiples and these parts' plateaus sit at round numbers, so a plane running along a face left 36 zero-area runs on the foot, each printed as 'the mesh has a gap here' - 36 false gap claims on a sound mesh. No-area runs are now one explanatory line, excluded from the outline count and the straightness comparison.
3. A facet was offered as a face. 507 of the handle's 592 flats are single triangles of a bent bar, each given a 'candidate: a face that leans is a loft()' line - wrong 545 times. One-triangle flats and sub-0.5 mm strips are now summed per block with no candidate offered. The agent tested and rejected a '1-2 triangles' threshold on the data, because the handle's largest two-triangle flats are real 20 mm-wide faces of 658 mm2.

Criterion #4 (intent never inferred) held throughout: the bores read as 4.000 mm bores, never as clearance holes for a named screw.

What this does NOT include, deliberately: there is no UI. `survey` and `report` are exported from `bench`, but nothing in web/ calls them - the only mention in main.ts is a comment. A maker reaches this by typing `print(report(survey(reference)))` into a script after dropping an STL. Raised as its own task rather than left implied by a closed parent.
<!-- SECTION:NOTES:END -->
