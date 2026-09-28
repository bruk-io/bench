---
id: task-87
title: 'The 3MF carries per-part slicer hints Bambu reads: brim, filament'
status: To Do
assignee: []
created_date: '2026-09-28 01:07'
labels:
  - export
dependencies:
  - task-86
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The tower's bottom coupon stands on a 10 mm edge and needs a brim, and every part knows its plastic - but the 3MF says neither, so both are set by hand in the slicer. Bambu Studio reads per-object settings from Metadata/model_settings.config in the 3MF. Let Printed(...) carry hints (e.g. brim=True, or derived when the footprint on the bed is thin), and write them plus the material name per object. Check the format against a 3MF saved by Bambu Studio itself before relying on any key; other slicers ignore the extra file.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Printed parts can ask for a brim; the 3MF sets it for that object in Bambu's model_settings.config, checked against a Bambu-saved 3MF
- [ ] #2 Each object names its filament type from the part's Material
- [ ] #3 The plain 3MF parts still open unchanged in other slicers
<!-- AC:END -->
