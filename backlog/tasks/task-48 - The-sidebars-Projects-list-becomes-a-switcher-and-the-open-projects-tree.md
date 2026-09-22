---
id: task-48
title: The sidebar's Projects list becomes a switcher and the open project's tree
status: To Do
assignee: []
created_date: '2026-09-22 15:29'
updated_date: '2026-09-22 15:30'
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
- [ ] #1 The container shows the open project's own files rather than a list of other projects
- [ ] #2 Switching to another project is one control, distinct from the file tree
- [ ] #3 Clicking a file opens it in the editor group, including a second script
- [ ] #4 Rename, delete and duplicate act on the row a person chose rather than on whatever is current
- [ ] #5 Delete says what will actually happen to the files on the host, and is recoverable rather than an unlink
- [ ] #6 A project that is open read-only shows its files and offers no action that would write
- [ ] #7 The rail, the container heading and the refs container's foot copy no longer describe the old shape
- [ ] #8 The e2e checks that drove the old buttons by id are rewritten against the new controls
<!-- AC:END -->
