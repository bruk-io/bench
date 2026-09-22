---
id: task-50
title: >-
  tools.build runs a project directory, and a script can import the modules
  beside it
status: To Do
assignee: []
created_date: '2026-09-22 15:30'
updated_date: '2026-09-22 15:30'
labels: []
milestone: m-4
dependencies:
  - task-46
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-9, steps 5 and 6. tools.build takes a script path and a TOML beside it; once a project is a directory it should take the directory, so the browser and the command line agree about what a project is without translating anything.

And with the project's files on the host, a script can finally be more than one file: the worker already writes bench into /lib from PY_SOURCES, so writing the project's own .py files beside them is the same move. This is the first time a maker can factor a long script into modules, and [project] entry is what says which one is the script.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 tools.build takes a project directory and runs its entry script with its values
- [ ] #2 tools.build still takes a bare script path, for a script with no project around it
- [ ] #3 A script in the browser can import another module from its own project
- [ ] #4 A module a script imports is not mistaken for the entry, and the entry is what a fresh open runs
- [ ] #5 An import naming a module that is not in the project fails with something that says so
- [ ] #6 The examples still run unchanged from both the app and the command line
<!-- AC:END -->
