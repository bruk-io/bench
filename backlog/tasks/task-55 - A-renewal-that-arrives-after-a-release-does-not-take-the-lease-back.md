---
id: task-55
title: A renewal that arrives after a release does not take the lease back
status: Done
assignee: []
created_date: '2026-09-23 05:25'
updated_date: '2026-09-23 12:18'
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
- [x] #1 A renewal received after its holder's release does not give that holder the lease again
- [x] #2 Opening a project still takes a free lease, and a reload still reclaims its own at once (task-47 AC#1, AC#4 unchanged)
- [x] #3 Tested against a real server by sending a release then a renewal from the same holder, in that order
- [x] #4 The close-the-writer's-tab e2e test is stable across repeated runs (say how many)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #11 (d69bf1c). New `renew` act in lease.ts: extends a lease only when the asker holds it, never creates one; a renew of a free or someone else's lease changes nothing and answers the standing, like `look`. `take` keeps create-when-free / extend-when-yours for opening and reload-reclaim. leasing.ts: a holder polls with `renew`, a reader or unheld tab with `take`. A renew answered 'not yours' -> held by someone else: become their reader (a slept laptop does not silently re-take); free: take it, as a reader would.

Tests: lease.test.ts 'never creates a lease with a renew'; adapter tests/adapter/test_projects_lease.py::test_a_renewal_that_arrives_after_its_holders_release_does_not_take_the_lease_back (release then renew, same holder, real server; another client can then take it). test_closing_the_writers_tab_... ran 20/20. Gate: vitest 355, pytest 948+1 skip x2, e2e 112.

Known limit, narrower, left open: a READER polls with `take`, and on pagehide it aborts its in-flight ask but sends no release (release() returns early unless it is the writer). If the writer releases and a reader closes in the same moment, a `take` the server already received can give the lease to the closing reader until it lapses. Self-correcting (expiry); a cheap fix would be to send the keepalive release on pagehide whatever this tab's standing, since releasing a lease you do not hold changes nothing.
<!-- SECTION:NOTES:END -->
