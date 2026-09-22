---
id: task-15.1
title: 'Lay the shell out: rail, sidebar, centre, bottom panel, status bar'
status: Done
assignee: []
created_date: '2026-09-22 16:53'
updated_date: '2026-09-22 19:04'
labels:
  - web
  - ux
dependencies: []
parent_task_id: task-15
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The furniture itself, with everything the app already does moved into it and still working.

A rail down the left whose icons switch what the sidebar is - VS Code's model, where an icon changes the sidebar's contents rather than firing a command. A sidebar hosting one container at a time. A centre holding the script and the 3D view. A panel across the bottom. A status bar under everything saying what the run amounts to.

The containers are the ones bench actually has rather than the ones a general editor would want: the scripts kept, the refs, the parameters, the sheets. Which container was last open is remembered, the way the app already remembers which tab was in front.

The parameters panel moves out of the centre and into the sidebar, which is the change a maker will feel most: it is a narrower column than the tab it had. That is the direction's own recorded cost of giving every surface a home, and the panel is to be laid out for the column it now lives in rather than left to spill.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The rail switches which container the sidebar shows, and marks which one is showing
- [x] #2 Which container was last open survives a reload
- [x] #3 The scripts kept, the parameters and the sheets each have a sidebar container, and the examples are reachable from one of them
- [x] #4 Run, stop, the run state and the keyboard shortcuts work as they did
- [x] #5 A dropped reference body still draws as a backdrop and its chip still names it
- [x] #6 The shell holds together at a narrow window rather than spilling
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The shell is a CSS grid of three rows (40px title bar, the shell, 24px status bar); the shell is a grid of rail (46) / sidebar (244) / centre. The centre is the two editor groups over the panel.

The rail switches containers rather than firing commands - `showContainer` hides every other `.container` and sets `aria-pressed` - and the choice is remembered under a new `bench.container` key (`bench.tab` is gone with the left pane's tabs). Problems is deliberately NOT a fifth container: the rail's Problems button reveals the bottom panel's Problems tab, so a finding keeps one home.

The parameters moved into the sidebar, so `bench-params` went from `repeat(auto-fill, minmax(300px, 1fr))` to a single `minmax(0, 1fr)` column - the panel is laid out for the 244px column it now lives in rather than spilling out of it.

Clicking the container already showing collapses the sidebar, but only where that means something: `matchMedia("(max-width: 1000px)")`, the width at which the sidebar takes the centre's place instead of sharing the row.

Checked against the merged app rather than taken from the build report. Each criterion has an e2e check behind it that I have watched pass in a full gate run on main: the rail switching the sidebar (`test_the_rail_switches_what_the_sidebar_is`), the open container surviving a reload (`test_which_container_was_open_survives_a_reload`), the rail's counts (`test_the_rail_counts_what_is_waiting_in_a_container`), the parameters living in a container (`test_the_parameters_live_in_the_sidebar_now`, `test_a_parameter_edit_regrows_the_geometry`), run/stop and the shortcuts (`test_the_stop_button_stops_a_running_script`, `test_the_insert_shortcut_writes_the_ref_once`), and the narrow layout holding together (`test_a_narrow_window_stacks_the_layout`).

The dropped-reference backdrop and its chip survive the rebuild - that path was added in #12 and is exercised by the printed-page e2e checks, which still pass.
<!-- SECTION:NOTES:END -->
