---
id: task-47
title: 'An open project is leased to one writer, and everyone else reads it'
status: In Progress
assignee: []
created_date: '2026-09-22 15:29'
updated_date: '2026-09-23 03:53'
labels: []
milestone: m-4
dependencies:
  - task-46
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-9. Once projects live on the host, two clients can hold one project at once - a desktop and a tablet, which is the setup this app is meant for. Without something deciding, a tab left open on yesterday's state can push it over the other machine's work, silently, because the app writes on every panel edit rather than on a Save.

The host grants a write lease on a project to one client. Everyone else may open, read, run and export it; nobody else may write. Because clients vanish without warning - a shut lid, a backgrounded tablet, a crash - it is a lease with an expiry that the holder renews, never a lock that outlives its owner.

It settles nothing about the maker's own editor: vim does not ask the route for permission. That is what the stale-write refusal in task-45 is for.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Opening a project takes the write lease when it is free
- [ ] #2 A second client opening the same project can read, run and export it but cannot write, and is told why
- [ ] #3 A lease whose holder stops renewing lapses on its own, and the project becomes writable again without anyone intervening
- [ ] #4 Reloading a tab reclaims that tab's own lease immediately rather than waiting for it to lapse
- [ ] #5 Closing a tab releases the lease promptly in the ordinary case, and correctness does not depend on that happening
- [ ] #6 A person can take a lease that is still held, having been told whose it is
- [ ] #7 A reader can turn knobs and see the result without those values being written anywhere
- [ ] #8 A server restart voids every lease and leaves nothing behind to clean up by hand
<!-- AC:END -->
