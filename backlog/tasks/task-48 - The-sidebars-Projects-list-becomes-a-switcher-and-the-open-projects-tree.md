---
id: task-48
title: The sidebar's Projects list becomes a switcher and the open project's tree
status: Done
assignee: []
created_date: '2026-09-22 15:29'
updated_date: '2026-09-23 05:24'
labels: []
milestone: m-4
dependencies:
  - task-46
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-9, step 3, and the original complaint: the Projects container is a flat list of .py names with six buttons under it that all act on "the current file". It is a switcher pretending to be an explorer, and it shows one of a project's files while naming the whole project after it.

Split the two controls. A switcher on one line names the open project and offers the others, which is the rare act. The rest of the container is the open project's own files - bench.toml, its scripts, and its references - each opening in the editor group on a click, with the actions that used to be a toolbar now belonging to the row they act on.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The container shows the open project's own files rather than a list of other projects
- [x] #2 Switching to another project is one control, distinct from the file tree
- [x] #3 Clicking a file opens it in the editor group, including a second script
- [x] #4 Rename, delete and duplicate act on the row a person chose rather than on whatever is current
- [x] #5 Delete says what will actually happen to the files on the host, and is recoverable rather than an unlink
- [x] #6 A project that is open read-only shows its files and offers no action that would write
- [x] #7 The rail, the container heading and the refs container's foot copy no longer describe the old shape
- [x] #8 The e2e checks that drove the old buttons by id are rewritten against the new controls
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #9 (ed6610a). The Projects container is a one-line switcher plus the open project's own files (bench.toml, scripts, meshes); a click opens a row; rename/duplicate/delete live on the row. Delete never unlinks: a file or a whole project directory moves to <root>/.trash/<YYYYMMDD-HHMMSS>-<project>[-N]/ and the prompt names that path and says how to get it back. New route ops: POST /__bench/projects/<project>?to= (rename the directory in one move) and DELETE /__bench/projects/<project> (to the trash); both check the lease on every name involved; movable() refuses a project that is a symlink and trashRoot() refuses a .trash that is not a plain directory. Fixes task-46's empty-dir and orphaned-STL leftovers and task-45's plain-unlink delete.

Read-only (task-47 reader): rows offer no writing action except Duplicate. A reader's 'saved to host' chip is now hidden unless it reports a refused write (task-47 follow-up). e2e rewritten against the new controls; #examples-button untouched so tools.qa and the e2e conftest are unchanged.

Known limits: renaming a script leaves a copy of the old name in .trash; duplicating a project does not copy its meshes; the directory rename checks the new name then renames (same kind of window task-45 documents).

Reviewed on main: route.ts decisions for the two new ops, movable()/trashed()/renamedProject() in server/projects.ts, delete-prompt screenshot. Agent's gate after merging main (task-50): vitest 349, pytest 945+1 skip x2, e2e 109, mypy 104.
<!-- SECTION:NOTES:END -->
