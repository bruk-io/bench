---
id: task-38
title: 'A project''s [reference] table is missing from its own .toml tab and download'
status: Done
assignee: []
created_date: '2026-09-22 01:49'
updated_date: '2026-09-22 01:46'
labels:
  - bug
  - web
milestone: Mesh Placement
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while researching task-37. `web/src/main.ts:197-198`'s `valuesDocument()` builds the project's `.toml` text from `{name, overrides}` only:

```ts
const valuesDocument = (project: { readonly name: string; readonly overrides: Overrides }): string =>
  toml(project.overrides, project.name, scene?.params.map((one) => one.name) ?? []);
```

`toml()` (in `values.ts`, extended by task-26 step 3) takes a fourth `reference` argument specifically so a `[reference]` table survives every regeneration - but `valuesDocument()` never passes it. Two consequences, both silent:

1. The visible read-only `.toml` tab (`showValues()`) never shows a project's `[reference]` table, even when one is applied and in effect - a maker has no in-app way to see what placement is actually active.
2. The downloaded project zip (`ui.download`'s handler, `main.ts:908`, also calls `valuesDocument()`) omits `[reference]` entirely from the exported `.toml` - so a maker who drops a reference mesh via a project opened with a placement, then downloads the project, gets a file silently missing the very fact decision-4 exists to keep written down.

This is exactly the failure decision-4's own acceptance criteria warn against: "nothing is moved silently... what the viewer draws and what the report says always agree." A downloaded project that no longer says how its own mesh was placed is a document disagreeing with itself.

Fix: thread `project.reference` through `valuesDocument()` to `toml()`'s fourth argument, the same way `serialized()` in `files.ts` already does correctly for the persisted (localStorage) copy - only the *rendered* and *downloaded* copies are missing it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Opening a project with a [reference] table shows it in the visible .toml tab
- [x] #2 Downloading a project with a [reference] table includes it in the exported .toml file, byte for byte what the app applied
- [x] #3 A project with no [reference] table is completely unaffected
<!-- AC:END -->
