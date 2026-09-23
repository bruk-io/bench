---
id: task-53
title: 'A check''s warning reaches the Problems panel, not only the log'
status: In Progress
assignee: []
created_date: '2026-09-23 01:18'
updated_date: '2026-09-23 01:19'
labels: []
milestone: m-5
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Running tools.qa over gridfinity_bin.py on 2026-09-22: web/qa/out/qa-log.txt records `violations  warning overhangs: a face leans 90 degrees off the build direction, and PETG holds up 45 (socket-1, line 257)` and the status bar says "1 part · 1 warning", yet the screenshot's Problems panel reads "Nothing was reported: the run is clean." The log line arrives about two seconds after `run finished`.

Either the panel is right and the screenshot was taken before the finding arrived (then tools.qa shoots too early and the fix is in tools/qa.py), or the panel really does not show a finding the status bar counts (a real bug in the app). Find out which before fixing either. The script's own docstring says `check_overhangs` is not called there - so also establish where the finding comes from.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 It is established, with evidence, whether the panel or the screenshot timing was wrong
- [ ] #2 A run whose status bar counts a warning shows that warning in the Problems panel
- [ ] #3 tools.qa's screenshot of a run shows what the run finally reported, not an earlier state
- [ ] #4 Covered by a test that fails on the old behaviour
<!-- AC:END -->
