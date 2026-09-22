---
id: task-33
title: Merged work is not visible in the app without somebody running a build
status: Done
assignee: []
created_date: '2026-09-22 22:41'
updated_date: '2026-09-22 13:26'
labels:
  - web
milestone: Hardening
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found for real: `examples/fulcrum_hinge.py` was merged to main and could not be opened in the browser. Two reasons, both invisible from the outside. `web/src/generated/pysources.ts` is gitignored and generated, so no merge or pull ever updates it - the copy in the working tree was a day old and contained `fulcrum_hinge` zero times. And the server on 4173 is `vite preview`, which serves the built `dist/`, which was two days old.

So the code was on main and was in nothing the browser could see. The honest answer to "can I load this file" was three build steps, and nothing anywhere said so.

The fix is not necessarily to build automatically. Detecting the staleness and saying it plainly would be enough, and is probably better than a hidden rebuild - the app knowing "the bundle is older than the examples on disk" is a fact it could show in the status bar or on the examples menu.

Small and self-contained. Depends on nothing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Pulling main and opening the app either shows the new examples, or says plainly that the bundle is stale and what to run
- [ ] #2 A stale bundle is never silently presented as the current set of examples
- [ ] #3 Whatever detects it works for a preview build as well as the dev server, since those go stale differently
- [ ] #4 The README says which command makes a merged example loadable
<!-- AC:END -->
