---
id: task-53
title: 'A check''s warning reaches the Problems panel, not only the log'
status: Done
assignee: []
created_date: '2026-09-23 01:18'
updated_date: '2026-09-23 01:51'
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
- [x] #1 It is established, with evidence, whether the panel or the screenshot timing was wrong
- [x] #2 A run whose status bar counts a warning shows that warning in the Problems panel
- [x] #3 tools.qa's screenshot of a run shows what the run finally reported, not an earlier state
- [x] #4 Covered by a test that fails on the old behaviour
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #3 (3a16d37). The app was never wrong: status bar and Problems panel are set from the same violations tuple in one synchronous call (received() in main.ts via views.py _summary()). The mismatch was tools.qa's own: a qa-log.txt from an earlier systainer_tote.py walk (16 Sep; its check_overhangs at line 257 warns on tote/socket-1) sat beside fresh screenshots from a walk that crashed on the hinge.py strict-mode locator bug before rewriting LOG.

Fixes: exact-name example locator in tools/qa.py and tests/e2e/conftest.py; tools.qa clears web/qa/out before a walk (_reset) and writes the log line by line. Tests: tests/functional/test_qa_tool.py::test_a_stale_log_does_not_survive_a_fresh_walk, e2e test_a_warning_the_status_bar_counts_is_in_the_problems_panel and test_an_example_whose_name_is_another_examples_prefix_still_picks_cleanly. Gate: pytest 876+1 skip x2, e2e 79, vitest 224. Reviewed diff and the systainer_tote screenshot (warning shown in panel).
<!-- SECTION:NOTES:END -->
