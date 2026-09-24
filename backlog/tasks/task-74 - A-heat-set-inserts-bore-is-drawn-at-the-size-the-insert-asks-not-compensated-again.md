---
id: task-74
title: >-
  A heat-set insert's bore is drawn at the size the insert asks, not compensated
  again
status: To Do
assignee: []
created_date: '2026-09-24 19:47'
labels: []
milestone: m-10
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found writing docs/printing.md (2026-09-24): fasteners.py documents an insert's bore as the hole to print (e.g. INSERT_M3.bore 4.2 mm, quoted the other way round from screw holes), but hole(insert=..., printed=...) still adds the material's hole_compensation, so an M3 insert gets 4.4 mm - loose enough to spin. The guide works round it (leave printed= out and pass top=Top.ROUND upright; subtract PLA.hole_compensation sideways). hole() should not compensate an insert bore; printed= should still decide its top. Fix, and change the guide's workaround to the plain call.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 hole(insert=INSERT_M3, printed=...) draws a 4.2 mm bore
- [ ] #2 printed= still chooses the bore's top by orientation
- [ ] #3 docs/printing.md's workaround replaced by the plain call
- [ ] #4 Unit test pins the bore size, and the enclosure example still builds
<!-- AC:END -->
