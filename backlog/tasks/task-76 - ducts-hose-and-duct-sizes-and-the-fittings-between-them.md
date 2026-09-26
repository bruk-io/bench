---
id: task-76
title: 'ducts: hose and duct sizes and the fittings between them'
status: Done
assignee: []
created_date: '2026-09-25 20:56'
updated_date: '2026-09-26 14:59'
labels:
  - library
milestone: m-11
dependencies:
  - task-70
  - task-73
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-11's first standards library. A flat module `bench/library/ducts.py`, beside `gridfinity` - no `parts/` package until the library outgrows a flat list (a rename then, when there are ~8 modules or two want the same name).

What the vent's manifold (projects/vent) had to build by hand, as calls: a size table of real hoses and ducts, and the fittings that join them at the fit table's slide - spigot, socket, coupler, reducer, elbow, branch, square-to-round. Built on m-10's `shell` and `sweep`, so a fitting is a path and a wall, not a pair of lofts subtracted.

Sizes are published numbers a print has to match, so each one cites where it comes from, and one that is measured or estimated says so - the fit goes wrong if it is guessed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `library/ducts.py` with a frozen size record (name, which side the nominal measures - inside or outside, and the diameter), and a table of common sizes, each with its source or marked as an estimate
- [x] #2 Fittings as functions returning solids: spigot (slides into a duct or hose), socket (a duct or hose slides into it), reducer, elbow (any angle, by sweep), branch (a wye), and square-to-round (a rectangular opening to a round one)
- [x] #3 A spigot or socket's diameter comes from the size and the fit table's slide, not a hard-coded gap; a fit test (`check_clearance_through`/`mated`) shows a spigot in a matching socket at the slide
- [x] #4 Every fitting is printable on the orientation it names: overhangs checked, wall no thinner than the material's minimum
- [x] #5 An example the gate runs, measured by the adapter tests
- [x] #6 library/__init__.py's docstring says what ducts is and that the library stays flat for now; README and DESIGN list the module
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Five sizes are estimates until measured: PORT_2_5, VAC_1_25, VAC_2_5, DUCT_4, DUCT_6 (for the last four, which side the nominal measures is a guess too). elbow() and branch() draw any turn; past max_overhang the overhang check flags it - two fittings and a coupler print instead. Turned fittings cannot be mated by face (no planes), so they are placed on a shared axis. A 6 in wye is taller than the H2D.
<!-- SECTION:NOTES:END -->
