---
id: task-50
title: >-
  tools.build runs a project directory, and a script can import the modules
  beside it
status: Done
assignee: []
created_date: '2026-09-22 15:30'
updated_date: '2026-09-23 04:41'
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
- [x] #1 tools.build takes a project directory and runs its entry script with its values
- [x] #2 tools.build still takes a bare script path, for a script with no project around it
- [x] #3 A script in the browser can import another module from its own project
- [x] #4 A module a script imports is not mistaken for the entry, and the entry is what a fresh open runs
- [x] #5 An import naming a module that is not in the project fails with something that says so
- [x] #6 The examples still run unchanged from both the app and the command line
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #8 (3a9ee3d). tools.build <project-dir> and --project NAME run [project] entry with [values]/[reference]; entry resolution (_entry_in) mirrors project-files.ts entryOf; decision-3's <script>.toml shape still works; unknown tables ignored; bare script path unchanged. This closes task-46's gap where the CLI ignored the app's bench.toml.

Project modules: bench.worker._mounted rebuilds <tmp>/bench-project from the open project's other .py files on EVERY run and pops any sys.modules entry loaded from there, so a project switched away from cannot leave a sibling importable. bench.shadow.shadowed (one rule for CLI and browser) refuses a project file named after a stdlib module or bench - it does not cover third-party packages in the runtime (numpy, manifold3d).

AC#5 is met minimally: a missing module shows `ModuleNotFoundError: No module named 'X'` in the Problems panel and CLI output - true, but it does not say 'not in this project'. A friendlier message is a possible follow-up.

Reviewed on main: shadow.py and worker.py mount/pop logic. Agent's gate: mypy 101, vitest 312, pytest 930+1 skip x2, e2e 102. Test hygiene note: tests that import project modules should use distinctive module names (a generic `parts` collided across test files in one pytest process).
<!-- SECTION:NOTES:END -->
