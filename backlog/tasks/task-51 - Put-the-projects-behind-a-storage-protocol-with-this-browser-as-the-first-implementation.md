---
id: task-51
title: >-
  Put the projects behind a storage protocol, with this browser as the first
  implementation
status: Done
assignee: []
created_date: '2026-09-22 17:17'
updated_date: '2026-09-22 17:17'
labels: []
milestone: m-4
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The app reads and writes projects through `localStorage` directly, at the page's top level and synchronously. decision-9 says they belong on the host, and a bucket may hold them after that - neither of which can answer synchronously, and neither of which should mean rewriting the page again.

Put a protocol between the app and the place: one interface, an implementation per place, and a document rather than a Workspace crossing it so `files.ts` stays the one pair of functions that parse and serialize projects. Retrofit what exists as the first implementation, changing no behaviour.

A seam is not a fallback. decision-9 is explicit that the app does not silently degrade from one place to another; a store is chosen once by whoever starts the app, never tried in order.

Only the projects go behind it. Which container the rail had open, whether the panel was shut, the log level and the hang fingerprint are about this browser on this device and stay where they are.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A project store is one interface with load and save, asynchronous, moving the kept document rather than a parsed workspace
- [x] #2 The browser's own storage is an implementation of it, keeping projects under the same key and losing nothing a browser kept before
- [x] #3 The page reads and writes projects only through the store, and nothing above the store knows which place it is
- [x] #4 Per-browser state - the rail's container, the panel, the log level, the hang fingerprint - is not carried by the store
- [x] #5 Editing a script or turning a knob does not wait on a write
- [x] #6 A write the place refuses is reported rather than swallowed, unlike the per-browser state which may be forgotten silently
- [x] #7 A store that cannot be read leaves the kept projects alone and says so, rather than starting from an empty workspace
- [x] #8 The app boots with the projects arriving asynchronously, and the checks that cover booting, the watchdog and the hang replay still pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`store.ts` is the protocol - `kind`, `load()`, `save(text)` - and `store-local.ts` is the browser's own storage behind it, under the same `bench.files` key so nothing a browser already kept is lost.

A document crosses the seam, never a `Workspace`. A store that returned a parsed workspace would make every future implementation re-own `restored()`'s two legacy shapes; moving the serialized text keeps `files.ts` the one parse/serialize pair and makes a host route or a bucket a matter of shifting bytes.

`load()` distinguishes "nothing kept" from "could not ask": `null` is a first visit, and a throw leaves the kept projects alone rather than overwriting them with an empty workspace on a blip.

`save()` stops swallowing. `storage.ts` is written never to throw, which is right for which tab was open and wrong for a person's projects, so the local store reads the key back and rejects on a write the browser declined.

`keep()` stayed synchronous - it is on every keystroke and every knob turn - and fires the write off, logging a failure. That is decision-9's outbox rule and it kept the retrofit to one call site rather than fifteen.

The boot restructure was the real work. `workspace` was initialised at module scope from a synchronous read, and the editor mounted with its source. Now the editor mounts empty, `boot()` awaits the store, replaces the document and clears the debounce that the replacement starts, and the hang check runs against the source that actually arrived.

Per-browser state stays in `storage.ts` and does not travel: the rail's container, the panel, the log level, the hang fingerprint. A panel left shut on a tablet is not a fact about the project.

Checked: 7 new tests on the local store, `tsc` and lint clean, and a full `uv run tools/check.py` green - 874 passed twice over and all 77 e2e, which is what covers the boot order, the watchdog and the hang replay.
<!-- SECTION:NOTES:END -->
