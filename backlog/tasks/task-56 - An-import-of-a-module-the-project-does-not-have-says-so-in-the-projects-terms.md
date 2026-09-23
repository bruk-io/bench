---
id: task-56
title: An import of a module the project does not have says so in the project's terms
status: Done
assignee: []
created_date: '2026-09-23 05:25'
updated_date: '2026-09-23 17:20'
labels: []
milestone: m-6
dependencies:
  - task-50
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
task-50 AC#5 is met minimally: `import sidekick` in a project with no sidekick.py shows Python's own `ModuleNotFoundError: No module named 'sidekick'` in the Problems panel and on the command line. True, but it does not say what a maker needs to know - that the project has no `sidekick.py`, and which modules it does have. Both the worker (src/bench/worker.py, project modules mounted per run) and tools.build know the project's files, so the message can say it in one place both use, the way bench.shadow keeps the shadowing rule in one place.

Also consider: bench.shadow refuses project files named after stdlib modules and bench, but not after third-party packages the runtime ships (numpy, manifold3d) - decide whether those belong in the reserved set.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A missing project-local import names the missing file and lists the project's own modules, in the app's Problems panel and on the command line
- [x] #2 An import of a genuinely missing third-party package is not described as a missing project file
- [x] #3 The decision about third-party names in bench.shadow is written down, with a test either way
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #12. bench.missing.explained(missing, modules) is the one rule the worker and tools.build share: a dotted name is a submodule question and Python's message stands; a name bench.shadow reserves (stdlib, bench, Pyodide's js/pyodide) says only the runtime lacks it; any other top-level name says both possibilities (no X.py in the project - listing what it has - and no X package in the runtime) rather than guessing. script.run gained modules= (None = no project, message untouched). Original ModuleNotFoundError text and traceback stay visible.

Reserved-set decision (in shadow.py): js and pyodide added; numpy and manifold3d NOT reserved - worker.ts loads no Pyodide packages and pyproject has no dependencies, so neither is importable in this runtime. Tests both ways. Gate: mypy 108, vitest 351, pytest 966+1 skip x2, e2e 112. Reviewed on main: PR body, pyproject import-boundary entry for the new module.
<!-- SECTION:NOTES:END -->
