---
id: task-45
title: Serve the host's projects directory over a route the app can read and write
status: Done
assignee: []
created_date: '2026-09-22 15:29'
updated_date: '2026-09-23 01:40'
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
- [x] #1 The host designates one projects root, resolved in one place, and tools/build.py reads the same root so the app and the command line cannot disagree
- [x] #2 The route lists projects, and reads, writes, creates, renames and deletes files within one
- [x] #3 A request naming a path outside the root is refused, including via .. , an absolute path and a symlink
- [x] #4 Only .py, .toml and .stl can be written
- [x] #5 A request from another origin is refused, so a page in another tab cannot write on the maker's behalf
- [x] #6 A read carries the file's modification time and a write whose base has moved is refused, saying which file moved, rather than overwriting
- [x] #7 The route answers in both npm run dev and npm run preview
- [x] #8 Covered by tests that drive a real server against a temporary root, including each refusal
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #2 (0b0951e). Pure decision in web/src/route.ts (URL split on literal / before decoding, each segment one plain name; host rule; origin rule), I/O edge in web/server/projects.ts, typed client web/src/host.ts, Python side tools/projects.py. Root is BENCH_PROJECTS (absolute only), default <repo>/projects (gitignored, created on start); a named root is never created.

Found on Vite 6.4.3: plugin middleware runs BEFORE Vite's own host check and CORS in both dev and preview, so allowedHosts never protected this route - the route applies Vite's host rule itself (hostRefused). bench:staleness has the same exposure (read-only).

Versions are SHA-256 of content (ETag / If-Match), not mtime - mtime is 1-2 s coarse on FAT/exFAT/SMB/HFS+ and a knob edit keeps the size. A read still carries mtime. Known, documented window: between hashing and rename another writer's edit can be lost.

No Origin header is allowed (non-browser clients); Sec-Fetch-Site same-site is refused (another port on the same machine is another tab's dev server).

For task-46: README must say plainly that with --host anyone on the LAN can reach the route; an mDNS name like workshop.local needs adding to allowedHosts; the web README's 'static' framing still needs its rewrite. Delete is a plain unlink until task-48.

Reviewed on main: read route.ts and server/projects.ts in full; reran tests/adapter/test_projects_route.py + tests/functional/test_build_tool.py (56 passed, real vite via tools/preview.served) and src/route.test.ts (26 passed). Agent's full gate: vitest 250, pytest 912+1 skip x2, e2e 79 - all up from baseline.
<!-- SECTION:NOTES:END -->
