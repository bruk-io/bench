---
id: task-78
title: 'check_overhangs reports every face past the limit, not only the worst'
status: To Do
assignee: []
created_date: '2026-09-26 16:06'
labels:
  - checks
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found moving the vent onto ducts (2026-09-26): check_overhangs names one face per part - the worst, and at a 90 degree tie the first it meets. Everything else goes unreported. On the vent that hid a 4 in side port lying on its side (88.7 degrees over 38 mm, needs support) behind a groove ledge, and hid task-77's phantom faces (3525 mm2 and 129 mm2 at 90 degrees). The agent had to write its own face lister to see them. A check whose job is to say what needs support must not hide one overhang behind another.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every face (or connected region of faces) leaning past the material's limit is reported, each with its lean, area/span and ref
- [ ] #2 Findings for one part stay readable: grouped per region, ordered by severity, without one line per triangle
- [ ] #3 A test with two separate overhangs of equal lean reports both; the vent-like case (a ledge plus a side tube) reports both
- [ ] #4 Existing callers (require, the Problems panel, ducts and examples' no-findings tests) still work
<!-- AC:END -->
