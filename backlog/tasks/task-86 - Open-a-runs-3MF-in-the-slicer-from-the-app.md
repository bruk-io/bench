---
id: task-86
title: Open a run's 3MF in the slicer from the app
status: To Do
assignee: []
created_date: '2026-09-28 01:07'
labels:
  - export
  - web
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Printing test coupons meant downloading a 3MF and opening it by hand. The host server runs on the maker's machine and Bambu Studio is installed there, so an "Open in slicer" button beside the 3MF (and per part) can do it: Python builds the 3MF as now; the browser posts its bytes to a new host route; the server writes it to projects/<name>/prints/ (gitignored) and launches the configured slicer with execFile (fixed argv, never a shell string; path confined to the project's prints/; localhost only). Slicer from bench.toml [print] slicer or BENCH_SLICER, default BambuStudio on macOS (`open -a`), xdg-open elsewhere. Also: Python arranges the parts on the chosen printer's bed with spacing, so the 3MF opens arranged. Bambu registers a bambustudioopen:// scheme - a fallback for a page with no host, to verify before relying on it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An Open in slicer button next to the 3MF (and per printed part) writes the file into the project's prints/ and launches the configured slicer with it
- [ ] #2 The server route refuses paths outside the project's prints/ and only answers localhost; the command is execFile with a fixed argv
- [ ] #3 The 3MF's parts are arranged on the printer's bed (python), each laid in its print orientation, and fit the bed
- [ ] #4 Tested without mocks: the route against a configured slicer that is a tiny script recording its argv; e2e clicks the button and finds the file and the launch
<!-- AC:END -->
