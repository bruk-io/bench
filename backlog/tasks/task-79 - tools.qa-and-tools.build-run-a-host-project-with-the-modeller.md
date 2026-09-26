---
id: task-79
title: tools.qa and tools.build run a host project with the modeller
status: To Do
assignee: []
created_date: '2026-09-26 16:06'
labels:
  - tools
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found moving the vent onto ducts: tools.qa only walks examples/ and cannot open a host project, and tools.build --project runs without the modeller, so every check that needs a kernel reads "unchecked". The agent drove tools.stack by hand and wrote its own screenshot driver. Projects are where real designs live; they should get the same screenshots and the same checks as examples.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 tools.qa takes --project NAME [entry.py ...] and screenshots each entry the way it does examples
- [ ] #2 tools.build can run an entry with the shipped modeller, so kernel checks report instead of reading unchecked
- [ ] #3 Tested with a fixture project
<!-- AC:END -->
