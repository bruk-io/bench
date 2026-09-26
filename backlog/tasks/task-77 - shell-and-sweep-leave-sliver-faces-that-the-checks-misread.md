---
id: task-77
title: shell and sweep leave sliver faces that the checks misread
status: Done
assignee: []
created_date: '2026-09-26 04:31'
updated_date: '2026-09-26 16:37'
labels:
  - checks
  - operations
dependencies:
  - task-70
  - task-73
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found building library/ducts (task-76), measured on the shipped kernel:

- Shelled pieces set end to end stay separate touching bodies; the checks read a spigot's underside as a 90 degree ceiling and a loft's rim as a 0.17 mm wall.
- A shelled sweep with a tilted open end leaves near-degenerate slivers: check_wall reads 0.64 mm on a 45 degree 4 in elbow in PLA, check_overhangs 50 degrees in ASA.
- A tap drilled straight into a run of its own size leaves the cutting tool's end as a sliver leaning 90 minus the tap angle.

ducts works around all three by construction (one hollow cut, sweeping the wall's ring, a tap that sets off up the run). Anyone calling shell/sweep directly meets the false findings. The vent (projects/vent funnel.py, manifold.py) joins a loft to a spigot tube face to face the same way, so some of its README's "short bridges" may be this.

Decide whether the fix is in the operations (fuse pieces, avoid slivers) or in the checks (ignore faces below an area or thickness), and measure both.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each of the three constructions above is reproduced in a measured test that fails today
- [ ] #2 After the fix, shell and sweep used the naive way give no false overhang or wall findings, and a real overhang or thin wall is still found
- [x] #3 ducts' workarounds are kept or simplified, with its tests still passing
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-26, from the vent: the vent's phantoms were at loft-to-plate (funnel, 3525 mm2 at 90 degrees) and loft-to-box (hopper, 129 mm2) joins, not at the spigot joins, which left only zero-area slivers. Both went away when ducts fittings overlapped what they join. A 3-triangle, 0.0001 mm2 sliver remains where the funnel's collar meets the window.

PR #27. Causes: (1) the modeller stored face-tagged bodies as f32 but moved them in f64, leaving 3 um gaps that kept touching pieces apart - every moved body is now rounded onto the f32 grid, a chain of moves composed first (adapters/browser.py, modeller.ts); (2) shell's extra leg past a leaning open end put a cavity ring on the end plane - the end leg itself now runs on; (3) a tap tangent to a same-size run leaves a facet lip within one chord's sag - check_overhangs groups leaning triangles into corner-sharing patches and drops a patch narrower than CHORD (cost: a drawn ledge under 0.05 mm is not reported). AC#2 met except shells unioned on a leaning plane: task-83.
<!-- SECTION:NOTES:END -->
