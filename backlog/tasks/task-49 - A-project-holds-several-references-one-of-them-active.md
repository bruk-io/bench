---
id: task-49
title: 'A project holds several references, one of them active'
status: To Do
assignee: []
created_date: '2026-09-22 15:30'
updated_date: '2026-09-22 15:30'
labels: []
milestone: m-4
dependencies:
  - task-44
  - task-46
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-9, step 4. A dropped body is one base64 string in main.ts that a second drop replaces, and the [reference] table names a file the app does not hold. Once a project is a directory (task-46), a mesh dropped into it is a file in that directory and can simply stay.

Hold every mesh dropped into a project; make exactly one of them active - the one survey, detect faces and the pick panel are about - and let the References rows from task-44 choose which. [reference] stays a single table naming the active one, because a placement is of one body against one origin and decision-4's grammar has no room for two.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A mesh dropped on the view is kept in the project and is still there after a reload
- [ ] #2 Dropping a second mesh adds it rather than replacing the first
- [ ] #3 Exactly one reference is active, and choosing a row in the refs container is what makes it so
- [ ] #4 The [reference] table names the active mesh, and a project whose table names a file it holds needs no guard about which file was dropped
- [ ] #5 Survey, detect faces and the pick panel all act on the active reference
- [ ] #6 A reference can be removed from a project, and what that does to the files is said before it is done
- [ ] #7 A project opened read-only can select and survey a reference without writing anything
<!-- AC:END -->
