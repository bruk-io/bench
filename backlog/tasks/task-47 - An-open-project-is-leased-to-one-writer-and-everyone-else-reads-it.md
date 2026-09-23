---
id: task-47
title: 'An open project is leased to one writer, and everyone else reads it'
status: Done
assignee: []
created_date: '2026-09-22 15:29'
updated_date: '2026-09-23 04:44'
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
- [x] #1 Opening a project takes the write lease when it is free
- [x] #2 A second client opening the same project can read, run and export it but cannot write, and is told why
- [x] #3 A lease whose holder stops renewing lapses on its own, and the project becomes writable again without anyone intervening
- [x] #4 Reloading a tab reclaims that tab's own lease immediately rather than waiting for it to lapse
- [x] #5 Closing a tab releases the lease promptly in the ordinary case, and correctness does not depend on that happening
- [x] #6 A person can take a lease that is still held, having been told whose it is
- [x] #7 A reader can turn knobs and see the result without those values being written anywhere
- [x] #8 A server restart voids every lease and leaves nothing behind to clean up by hand
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #7 (627663e). Pure lease rules in web/src/lease.ts; /__bench/leases/<project> in route.ts (GET look, POST ?act=take|take-over|release; same host/origin rules); leases held in the middleware's memory (restart voids them, nothing on disk); every write/create/rename/delete carries X-Bench-Holder and the route refuses a held project's change from anyone else with `leased` (423). No holder header = somebody else when held; an unheld project is anybody's (curl, tools.qa, seeding still work). web/src/leasing.ts: take on open, renew at the server's renewMs, readers re-ask on the same cadence, keepalive release on pagehide, holder id = 16 random bytes in sessionStorage (reload reclaims).

Timing is PROVISIONAL, decision-9's shape and still the owner's call: EXPIRY_MS 60_000, renewal expiry/4 = 15 s, in lease.ts; BENCH_LEASE_MS overrides (tests). A reader's knobs change only the run's table, never the workspace (the store writes the whole diff); keep() refuses a change to a project this tab does not hold. Take-over is an in-page two-step naming the holder's label and address; the old writer is told.

Known limits: a duplicated tab copies sessionStorage and shares the holder id; a reader's view is as of open and does not follow the writer live (re-read when it becomes the writer). Small UI follow-up: a reader's status bar still shows the 'saved to host' chip beside 'read-only', which reads oddly when nothing it does is saved.

Reviewed on main: PR body, reader screenshot. Merged after task-50 (#8) - both touch main.ts - and reran tests/e2e/test_write_lease.py + test_project_modules.py + test_project_directory.py + test_host_store.py on the combined main: 25 passed. Agent's gate: vitest 336, pytest 926+1 skip x2, e2e 105, mypy 101.
<!-- SECTION:NOTES:END -->
