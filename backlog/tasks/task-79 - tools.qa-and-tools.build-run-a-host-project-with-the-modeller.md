---
id: task-79
title: tools.qa and tools.build run a host project with the modeller
status: Done
assignee: []
created_date: '2026-09-26 16:06'
updated_date: '2026-09-27 18:23'
labels:
  - tools
milestone: m-12
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found moving the vent onto ducts: tools.qa only walks examples/ and cannot open a host project, and tools.build --project runs without the modeller, so every check that needs a kernel reads "unchecked". The agent drove tools.stack by hand and wrote its own screenshot driver. Projects are where real designs live; they should get the same screenshots and the same checks as examples.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 tools.qa takes --project NAME [entry.py ...] and screenshots each entry the way it does examples
- [x] #2 tools.build can run an entry with the shipped modeller, so kernel checks report instead of reading unchecked
- [x] #3 Tested with a fixture project
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #28. tools.qa --project NAME [script ...] serves a temp copy of the project (the app writes into what it opens) and shoots view+Problems, Problems, parameters, files. tools.build --modeller runs inside Pyodide via tools.stack: a flag, not default - 13.4 s vs 0.12 s on the vent; a plain run ends with an 'N unchecked ... --modeller measures them' hint. Fixture project is text in tests/fixture_project.py. Known: tools.build doesn't pre-bind gridfinity as the browser does.
<!-- SECTION:NOTES:END -->
