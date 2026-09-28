---
id: task-96
title: The first run after a page load is stopped at 15 s though the script takes 8
status: Done
assignee: []
created_date: '2026-09-28 12:22'
updated_date: '2026-09-28 13:56'
labels:
  - web
  - worker
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reproduced 2026-09-28 on projects/tower coupon.py (a 5-piece reference fixture of ~250k triangles, 17-pose fit walks): the first run after the page loads is stopped by the 15 s limit ('the script did not finish in 15 s and was stopped'); pressing Run again in the same tab finishes in 8.2 s. So one-off warm-up - Pyodide imports, Manifold's first use, moving and parsing the reference mesh into the worker, whatever else - is counted against the script's budget. The limit exists to stop a runaway script, not to punish a cold start. Also seen: on a reader tab the reference named in bench.toml was not active until clicked, so the first run failed with 'no reference: bench.toml's [reference] should name fixture.stl' - check whether that is a task-88 regression.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The first and second runs are measured phase by phase and the numbers are in the PR
- [x] #2 The time limit counts only the script's own run; one-off warm-up (runtime start, imports, reference loading) is excluded or done before the clock starts, without letting a genuinely runaway script live past the limit
- [x] #3 tower's coupon.py (or an equivalent heavy fixture in tests) completes on a cold page load
- [x] #4 A reference named in bench.toml is active on opening a project in a reading tab as well as a writing one, or the reason it is not is documented and the run says so plainly
- [x] #5 e2e covers a cold first run with a large reference
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #42. Cause: the watchdog started when Run was pressed, so it counted whatever the worker was busy with - on tower, the ~155 s survey of the reference that starts on open. Now the worker posts 'started' and the clock starts there; a run pressed during a survey or detection replaces the worker, runs first, then re-sends the survey; a superseded runaway still dies. Runner.hold reads and places the reference before the clock, and keeps the last body. The reading-tab symptom predates task-88: a remembered runaway hash (localStorage, shared across tabs) returned before the reference was read. Cold tower run: 9.5 s round trip, script ~7.9 s (fit walks ~7 s). Survey speed: task-97.
<!-- SECTION:NOTES:END -->
