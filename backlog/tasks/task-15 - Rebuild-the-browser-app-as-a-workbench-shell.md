---
id: task-15
title: Rebuild the browser app as a workbench shell
status: Done
assignee: []
created_date: '2026-09-22 16:53'
updated_date: '2026-09-22 01:48'
labels:
  - web
  - ux
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The UX exploration compared five whole-app directions and the maker picked "Workbench": the shell a maker already knows from VS Code and Obsidian, worked out for what bench actually has.

Today the app is a header, two panes and a report card floating over the drawing. Every surface bench needs - the scripts kept, the refs a run named, the parameters it declared, the sheets it nested, what the checks found, what the script printed, the files it made - is either crammed into one of those two panes, hidden behind a popover, or covering the drawing. There is no canonical home for anything, so each new surface has been squeezed in beside the last.

The workbench gives each surface a home a maker can predict: a rail that switches what the sidebar is, a centre that holds the script and the 3D view, a bottom panel for what a run said, and a status bar for what it amounts to. The one thing bench has that nothing else does - a ref round-trip where clicking a face reveals it in a tree and clicking the tree highlights the face - gets a surface built for it rather than a status line.

The direction's own recorded costs are real and are not to be pretended away: this is furniture built for hundreds of files and bench has one script and seven examples, chrome eats all four edges, and this direction gives the 3D view less room than any other candidate. The build is to be designed against those, not in spite of them.

Nothing a maker can do today may be lost on the way: the editor, the parameters, run and stop, examples and files, export, the report, ref selection, the insert shortcut, the 3D view and a dropped reference body all keep working.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The app is a rail, a sidebar, a centre, a bottom panel and a status bar, and each surface has exactly one home
- [x] #2 Every feature the app had before the rebuild still works
- [x] #3 Clicking a face in the 3D view reveals that ref in the sidebar tree, and clicking the tree highlights the face
- [x] #4 The question of whether the 3D view is a tab or a pane that never yields is answered, implemented, and the reasoning written down
- [x] #5 The e2e suite tests the new structure honestly rather than being loosened until it passes
- [x] #6 uv run tools/check.py passes in full, and the web typecheck, lint and component tests pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #14, with #16 after it fixing the refs tree at a run's real scale. Four of the five subtasks are Done and verified against the merged app rather than against the build report: 15.1, 15.3, 15.4 and 15.5.

This parent stays In Progress on purpose. Criterion #3 - clicking a face reveals the ref in the tree and clicking the tree highlights the face - works in both directions and is covered by e2e, but 15.2 carries one criterion that shipped unmet: the mark on a row a check reported never fires, because a finding names the measured face in the solid's namespace while the tree holds part-qualified paths. That is not a UI defect and cannot be fixed in `web/`; it is now task-17.

On #4, the open question: the 3D view is a pane that never yields, and cut sheets open as tabs in the editor group beside the script. The reasoning is recorded in 15.4 - a tab strip promises any tab can be in front, and the view is the one surface every other surface addresses.

Closed now, and #3 with it. The note above says this parent stays open because 15.2 shipped one criterion unmet - that is no longer true. #19 (task-17) closed it by teaching the run which shape each check was handed, so a finding's refs arrive in the scene's own namespace, and the e2e assertion that had been withdrawn is a real check again: with the enclosure's wall at 1.2 mm, `box`'s row carries the flag and `lid`'s does not.

#3 itself - the round-trip in both directions - has been covered all along by `test_clicking_a_face_reveals_that_ref_in_the_tree` and `test_clicking_the_tree_lights_up_what_it_names`, both watched passing in full gate runs on main. It was held unticked only because the marking half of the same surface was broken.

All five subtasks are Done: 15.1 the shell, 15.2 the refs container and the round-trip, 15.3 the bottom panel, 15.4 sheets as tabs beside the script, 15.5 the e2e suite. Two defects found after the merge were fixed rather than left: the refs tree opening as hundreds of face rows at a run's real scale (task-16, #16), and a selection the newest run no longer names staying selected - implemented but untested until now.

The direction's recorded cost stands and is not pretended away: the 3D view gets about 32% of a 1440x900 window, and quiet mode - the thing the canvas proposed to make that payable - is designed but unbuilt.
<!-- SECTION:NOTES:END -->
