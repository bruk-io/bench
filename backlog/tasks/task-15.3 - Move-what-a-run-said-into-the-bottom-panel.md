---
id: task-15.3
title: Move what a run said into the bottom panel
status: Done
assignee: []
created_date: '2026-09-22 16:54'
updated_date: '2026-09-22 19:05'
labels:
  - web
  - ux
dependencies: []
parent_task_id: task-15
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Everything a run reports gets one home across the bottom, as tabs: what the checks found, what the script printed on each of its two streams, and the files the run made.

Today this is a card floating over the drawing that decides for itself when to come up, plus a popover on the viewer bar holding the downloads. Both exist because there was nowhere to put them. With a panel there is somewhere, and the rules can be simpler: the panel says what there is on each tab and a maker opens the one they want.

The two streams stay two tabs, not one box with both in it - a script's stderr is the thing it did not expect to have to say, and running it together with what it meant to print is how a warning goes unread. A finding carries the line of the script that asked for the check, and that line is a way back to the editor rather than a number to read out.

The panel can be put away when the drawing matters more than what was said, and the rail says how many problems are waiting either way.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The panel has a tab each for the checks' findings, the two streams, and the files a run made, each saying how many it holds
- [x] #2 A failed run and a check's finding are both reported there, with the geometry from the last good run still drawn
- [x] #3 A finding with a line takes the maker to that line of the script
- [x] #4 Every file a run made can still be downloaded one at a time or all at once
- [x] #5 The panel can be collapsed and brought back, and how many problems wait is visible with it collapsed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`bench-panel` replaces both `bench-report` (the card that floated over the drawing) and `bench-export-menu` (the popover on the viewer bar). The export menu's grouping logic came out into `exports.ts` as pure data - `layout(sheets, files)` over `Row`/`Download` - so the panel's Files tab and anything else can share it.

The two streams are two tabs rather than one box with both in it. Each tab says what it holds: a number for the findings and the files, a dot for a stream that said anything at all.

A finding's line number became a jump: `bench-violation` renders it as a button that sends `goto-line`, and the page brings the script forward and moves the cursor there (new `editor.goTo`, which clamps rather than throwing for a line past the end of an edited document).

Watch the whitespace in that row: the first version built `.where` as a multi-line template, which put a newline and eight spaces inside `textContent` - the rendered line looked right and read as "lid/wall-0 · \n line 12". It is one expression now, with no whitespace between its parts.

Verified against the merged app by the e2e checks, all watched passing in a full gate run on main: the two streams on tabs of their own (`test_the_panel_keeps_the_two_streams_on_tabs_of_their_own`), a clean run saying so rather than showing an empty panel (`test_a_clean_run_says_so_rather_than_showing_an_empty_panel`), a failed run bringing the panel forward by itself while the last good geometry stays drawn (`test_a_failed_run_brings_the_panel_forward_by_itself`, `test_a_run_that_fell_over_still_shows_what_it_printed`), a finding's line number taking you to that line (`test_a_findings_line_number_takes_you_to_it`), the files downloadable one at a time or as a zip from a panel tab (`test_a_sheet_downloads_as_svg`, `test_the_zip_holds_every_file_and_opens`, `test_the_downloads_wait_on_a_tab_of_the_panel`), and the panel collapsing and coming back (`test_the_panel_can_be_put_away_and_brought_back`).

One defect found while the panel was being built and fixed there: the collapsed state was read from storage but never written, so `bench.panel` was a dead key.
<!-- SECTION:NOTES:END -->
