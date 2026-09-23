---
id: task-55
title: A renewal that arrives after a release does not take the lease back
status: To Do
assignee: []
created_date: '2026-09-23 05:25'
labels: []
milestone: m-6
dependencies:
  - task-47
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
task-47's lease: a tab renews by asking to `take` again. If a renewal is already on the wire when the tab closes, the server can receive the keepalive release first and the renewal second - and the renewal re-takes the lease for a tab that no longer exists, so the project stays read-only for everyone else until it lapses (up to EXPIRY_MS). task-49 cancels an in-flight renewal on pagehide (AbortSignal), which narrows this but cannot stop a request the server already has. It caused one flaky run of `test_closing_the_writers_tab_lets_the_reader_have_it_well_before_the_lease_would_lapse`.

Fix it on the server: a renewal should only extend a lease its holder still holds, never create one - e.g. a distinct `renew` act, or a release that remembers the released holder id until its lease would have expired. Correctness already does not depend on release (AC#5 of task-47); this is about the ordinary case being prompt every time.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A renewal received after its holder's release does not give that holder the lease again
- [ ] #2 Opening a project still takes a free lease, and a reload still reclaims its own at once (task-47 AC#1, AC#4 unchanged)
- [ ] #3 Tested against a real server by sending a release then a renewal from the same holder, in that order
- [ ] #4 The close-the-writer's-tab e2e test is stable across repeated runs (say how many)
<!-- AC:END -->
