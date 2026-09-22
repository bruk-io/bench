---
id: task-45
title: Serve the host's projects directory over a route the app can read and write
status: To Do
assignee: []
created_date: '2026-09-22 15:29'
labels: []
milestone: m-4
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-9, step 2a. The app keeps projects in localStorage, which means they are not on disk, not in git, not readable by tools.build, and not reachable from a second device. decision-9 settles that a project is a directory under a root the host designates, reached over a small route on the server that already serves the page.

The route is a middleware beside bench:staleness, registered in both configureServer and configurePreviewServer so dev and preview both have it and tools/preview.py inherits it. It reads and writes files on somebody's machine, so what it will and will not do has to be decided here rather than later.

This task is the route and its client only - nothing in the app switches over to it yet.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The host designates one projects root, resolved in one place, and tools/build.py reads the same root so the app and the command line cannot disagree
- [ ] #2 The route lists projects, and reads, writes, creates, renames and deletes files within one
- [ ] #3 A request naming a path outside the root is refused, including via .. , an absolute path and a symlink
- [ ] #4 Only .py, .toml and .stl can be written
- [ ] #5 A request from another origin is refused, so a page in another tab cannot write on the maker's behalf
- [ ] #6 A read carries the file's modification time and a write whose base has moved is refused, saying which file moved, rather than overwriting
- [ ] #7 The route answers in both npm run dev and npm run preview
- [ ] #8 Covered by tests that drive a real server against a temporary root, including each refusal
<!-- AC:END -->
