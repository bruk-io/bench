---
id: task-52
title: >-
  Reach the projects over the host route, with an outbox for writes that have
  not landed
status: In Progress
assignee: []
created_date: '2026-09-22 20:21'
updated_date: '2026-09-23 01:56'
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
- [ ] #1 The host route is an implementation of the same project store interface, and nothing above the store knows which implementation it has
- [ ] #2 Editing a script or turning a knob does not wait on the network
- [ ] #3 A write that has not reached the host survives a reload and is drained when the host is reachable again
- [ ] #4 Several edits to the same thing while the host is unreachable do not become several writes when it returns
- [ ] #5 A write the host refuses as stale is reported rather than retried until it wins
- [ ] #6 The person can tell whether their work has reached the host
- [ ] #7 A dropped mesh is sent straight through rather than queued, since it is never edited
- [ ] #8 Which store the app is using is decided in one place, and a browser-kept project and a host-kept one are never both live at once
<!-- AC:END -->
