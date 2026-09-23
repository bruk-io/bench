---
id: task-49
title: 'A project holds several references, one of them active'
status: Done
assignee: []
created_date: '2026-09-22 15:30'
updated_date: '2026-09-23 05:24'
labels: []
milestone: m-4
dependencies:
  - task-44
  - task-46
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-9, step 4. A dropped body is one base64 string in main.ts that a second drop replaces, and the [reference] table names a file the app does not hold. Once a project is a directory (task-46), a mesh dropped into it is a file in that directory and can simply stay.

Hold every mesh dropped into a project; make exactly one of them active - the one survey, detect faces and the pick panel are about - and let the References rows from task-44 choose which. [reference] stays a single table naming the active one, because a placement is of one body against one origin and decision-4's grammar has no room for two.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A mesh dropped on the view is kept in the project and is still there after a reload
- [x] #2 Dropping a second mesh adds it rather than replacing the first
- [x] #3 Exactly one reference is active, and choosing a row in the refs container is what makes it so
- [x] #4 The [reference] table names the active mesh, and a project whose table names a file it holds needs no guard about which file was dropped
- [x] #5 Survey, detect faces and the pick panel all act on the active reference
- [x] #6 A reference can be removed from a project, and what that does to the files is said before it is done
- [x] #7 A project opened read-only can select and survey a reference without writing anything
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #10 (882ea8d). Every dropped mesh stays in the project dir and survives a reload; a second drop adds a row; exactly one is active, chosen by its row in the refs container (REFERENCES section above the run's refs); [reference] stays one table naming the active mesh (just `file` until a pick adds placement); tools/build.py hands over a named-only mesh as exported. Survey, detect faces and the pick panel act on the active one. Removing a reference goes through task-48's trash and says first that [reference] is cleared with it if it was active. A reader can choose and survey without writing.

OWNER'S CALL, open: choosing another mesh as active discards the previous mesh's placement, since [reference] holds one placement (decision-4's grammar); the refs container says so, but does not ask first. Options: ask first, or keep per-mesh placements somewhere (a grammar change to decision-4).

Also shipped here: the lease's in-flight renewal is cancelled when a tab lets go (AbortSignal on host.lease), narrowing the race behind one flaky run of test_closing_the_writers_tab... A renewal the server has already received can still re-take the lease after the release - see the follow-up task.

PR #10 conflicted after #9 was squash-merged (it was built on task-48's commits). Resolved on the branch with a merge of main keeping the branch side; git's auto-merge duplicated the Trashed interface in host.ts, removed by hand; the resulting tree was byte-identical to the agent's gated task-49 tree. Agent's gate: vitest 351, pytest 947+1 skip x2, e2e 112, mypy 105. Reviewed the two-references screenshot.
<!-- SECTION:NOTES:END -->
