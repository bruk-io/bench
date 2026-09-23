---
id: task-52
title: >-
  Reach the projects over the host route, with an outbox for writes that have
  not landed
status: Done
assignee: []
created_date: '2026-09-22 20:21'
updated_date: '2026-09-23 03:07'
labels: []
milestone: m-4
dependencies:
  - task-45
  - task-51
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
task-51 put the projects behind a protocol and implemented it for this browser. This is the other implementation: the same interface over the host route from task-45, so the page reaches a person's projects on the machine rather than in the tab.

With it comes the one thing a remote store needs that a local one did not. The app writes on every keystroke and every knob turn, and `keep()` is deliberately synchronous, so a write that has not reached the host yet has to live somewhere until it does. That is an outbox in IndexedDB - bounded by what is in flight, coalesced on the cadence the run already debounces at, drained when the host is reachable.

An outbox, never a mirror. The host is the truth; the browser holds only what has not got there yet. There is no merge and no conflict resolution here: a queue drains, and a drain onto a file that moved is refused by the route's own stale-write check (task-45) rather than resolved.

IndexedDB rather than localStorage: no five-megabyte wall, it holds binary without base64, and it is available on a plain-http origin on the LAN, which the origin private filesystem is not.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The host route is an implementation of the same project store interface, and nothing above the store knows which implementation it has
- [x] #2 Editing a script or turning a knob does not wait on the network
- [x] #3 A write that has not reached the host survives a reload and is drained when the host is reachable again
- [x] #4 Several edits to the same thing while the host is unreachable do not become several writes when it returns
- [x] #5 A write the host refuses as stale is reported rather than retried until it wins
- [x] #6 The person can tell whether their work has reached the host
- [x] #7 A dropped mesh is sent straight through rather than queued, since it is never edited
- [x] #8 Which store the app is using is decided in one place, and a browser-kept project and a host-kept one are never both live at once
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #5 (ef7c391). web/src/outbox.ts (IndexedDB, one row per file = pending queue + version cache; coalesces latest-text/first-base per project/file; one in-process lock around get-then-put; moved/exists/name/origin reported not retried; no-root/failed retried with backoff + online), web/src/store-host.ts (same ProjectStore interface; load overlays pending outbox rows then drains), web/src/project-files.ts (pure mapping + diff), chosenStore() in main.ts, #reach chip in the status bar (kept in this browser / saved to host / saving to host / not yet reached host / <file> refused).

INTERIM MAPPING - task-46 must replace it: every project lives in ONE host directory `workspace/` as <name>.py + <name>.toml, plus `_workspace.toml` recording which project is open. Two problems for task-46: (1) decision-9 wants one directory per project with bench.toml; (2) the open project is per-client state - kept on the host it makes one device's switch move the other's (task-47's desktop+tablet case). Keep 'which project is open' in the browser, not on the host.

Store rule (AC#8): host store only if the route answers ok AND workspace/ already exists, or this browser's outbox holds unlanded host work; otherwise local. So today nothing switches to the host by itself - task-46's adoption flow is what creates the host projects.

AC#7 is met at the store layer only: outbox.sendThrough bypasses the queue, but main.ts's drop handler does not call it yet (a dropped mesh is still session-only). Wiring it is task-46 AC#7 / task-49.

Reviewed on main: PR body, status-bar screenshots (all states labelled in words), reran src/outbox.test.ts + src/project-files.test.ts (34 passed) and tests/e2e/test_host_store.py (4 passed). Agent's gate: vitest 22 files/284, pytest 914+1 skip x2, e2e 86.
<!-- SECTION:NOTES:END -->
