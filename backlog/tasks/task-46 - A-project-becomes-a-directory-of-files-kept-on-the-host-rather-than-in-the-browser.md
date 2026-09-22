---
id: task-46
title: >-
  A project becomes a directory of files, kept on the host rather than in the
  browser
status: To Do
assignee: []
created_date: '2026-09-22 15:29'
updated_date: '2026-09-22 20:21'
labels: []
milestone: m-4
dependencies:
  - task-45
  - task-52
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-9, step 2b. With the route in place (task-45) and the projects reachable over it (task-52), the app's own model of a project follows: from {name, source, overrides, reference} kept as one document to a directory of named files with a bench.toml holding [project], [values] and [reference].

This retires the browser as a place projects live, and retires the web README's promise that everything is static: a build with no host behind it is not a degraded bench, it says it has no host. A browser holding projects from before this is adopted once, on first connect, and adoption writes real files to a real disk, so it asks before it does.

The outbox is not here. Writes that have not reached the host yet are the store layer's business (task-52), which is where the protocol from task-51 already put them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A project is a directory of files with one bench.toml, and the values a panel edit writes land in that file on the host
- [ ] #2 The entry script is named in bench.toml and the script a person has open is the one that runs
- [ ] #3 An older bench.toml, or one carrying tables this version does not know, still opens
- [ ] #4 Projects kept in this browser from before are adopted once, after asking, naming the directory to be created
- [ ] #5 The app says plainly when there is no host rather than appearing to work
- [ ] #6 The web README no longer claims the app is static, and says how to serve it for another device on the network

- [ ] #7 A dropped mesh is written into the project's own directory
<!-- AC:END -->
