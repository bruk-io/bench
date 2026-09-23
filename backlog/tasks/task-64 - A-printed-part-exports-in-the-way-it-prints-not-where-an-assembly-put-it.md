---
id: task-64
title: 'A printed part exports in the way it prints, not where an assembly put it'
status: In Progress
assignee: []
created_date: '2026-09-23 17:50'
updated_date: '2026-09-23 21:33'
labels: []
milestone: m-7
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by task-59 (2026-09-23): a printed part's STL and 3MF are its mesh written exactly where the script put it, and nothing on the way out reads Orient. So a part posed in an assembly - the enclosure example's lid (Orient(up=-Z)), or anything mated() turns over - exports in its assembly pose, not lying on the bed the way it prints. decision-10 says print orientation stays apart from where a part sits in an assembly; task-59's mating turns Orient.up with the body so the checks read it right, but the files still come out posed.

Export each printed part laid on the bed by its Orient (up, and bed_face when given): rotated so `up` is +Z and moved so its lowest point is z = 0, in the STL and in each 3MF object - while the app's view keeps showing the assembly pose.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A printed part's STL and 3MF lie on the bed the way its Orient says, whatever the assembly pose
- [ ] #2 The enclosure lid exports lip-up, and a part mated upside down exports as it was authored
- [ ] #3 The 3D view still shows parts where the assembly put them
- [ ] #4 Functional tests on the exported bytes
<!-- AC:END -->
