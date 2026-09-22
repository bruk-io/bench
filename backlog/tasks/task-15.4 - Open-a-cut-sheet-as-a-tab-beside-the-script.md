---
id: task-15.4
title: Open a cut sheet as a tab beside the script
status: Done
assignee: []
created_date: '2026-09-22 16:54'
updated_date: '2026-09-22 19:04'
labels:
  - web
  - ux
dependencies: []
parent_task_id: task-15
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A nested sheet is a drawing a maker reads before they cut, and today the only place it is ever seen is a 64-pixel thumbnail in a download popover. The centre already has a tab strip; a sheet becomes a tab in it, opened from the sidebar's sheets container.

This is also where the direction's sharpest unresolved question gets answered in code: whether the 3D view is a tab that a sheet can replace, or a pane that never yields. Whichever it is, the answer has to be the same everywhere - a maker must never click a ref and highlight a face on a surface that is not on screen.

A sheet tab can be shut. Sheets a run no longer makes do not leave tabs behind pointing at nothing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A sheet opens from the sidebar as a tab in the centre and draws its nest large enough to read
- [x] #2 A sheet tab can be closed, and the script cannot be closed out from under the maker
- [x] #3 A run that no longer makes a sheet leaves no tab pointing at it
- [x] #4 Opening a sheet never hides the surface that ref selection highlights
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Answered: the 3D view is a PANE THAT NEVER YIELDS, and cut sheets open as tabs in the editor group beside the script.

The reasoning is that a tab strip promises any tab can be the one in front, and the view is the single surface every other surface addresses - the refs tree reveals into it, the editor's cursor-ref highlight lights geometry in it, and Cmd-I reads the selection out of it. A peer that can be closed turns all three into silent no-ops. It also makes the direction's own recorded worst case worse: this shape already gives the view less room than any other candidate, and a closable view reaches zero.

So the script group owns the tab strip. `keepSheetTabs` drops tabs for sheets a new run no longer makes and falls back to the script, so no tab points at nothing; the script tab carries no close button.

Cut sheets open as tabs in the *editor* group, beside the script, rather than beside the 3D view - which is the consequence of ruling that the view is a pane and never a tab. Putting them beside the view would have meant picking a sheet yields the view, the exact failure that ruling prevents, and #4 is the criterion that says so.

Backed by `test_a_sheet_opens_as_a_tab_beside_the_script` and `test_a_sheet_tab_closes_and_the_script_cannot` in the e2e suite, both passing on main.
<!-- SECTION:NOTES:END -->
