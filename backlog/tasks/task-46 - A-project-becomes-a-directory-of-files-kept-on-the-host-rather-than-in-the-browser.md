---
id: task-46
title: >-
  A project becomes a directory of files, kept on the host rather than in the
  browser
status: Done
assignee: []
created_date: '2026-09-22 15:29'
updated_date: '2026-09-23 03:52'
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
- [x] #1 A project is a directory of files with one bench.toml, and the values a panel edit writes land in that file on the host
- [x] #2 The entry script is named in bench.toml and the script a person has open is the one that runs
- [x] #3 An older bench.toml, or one carrying tables this version does not know, still opens
- [x] #4 Projects kept in this browser from before are adopted once, after asking, naming the directory to be created
- [x] #5 The app says plainly when there is no host rather than appearing to work
- [x] #6 The web README no longer claims the app is static, and says how to serve it for another device on the network

- [x] #7 A dropped mesh is written into the project's own directory
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged as #6 (616eb8b). A project is <root>/<name>/ with its scripts and one bench.toml ([project] entry, [values], [reference]). task-52's interim workspace/ + _workspace.toml are gone; which project/script is open is per-browser (bench.open), so switching writes nothing to the host. When the route answers, the host is the store; the old localStorage store is read once, for adoption (in-page prompt naming every directory; accept/decline/not-asked-again tested), and bench.files is left in place.

AC#2 matched decision-9: entry opens by default; every script gets a tab and the open one runs without changing entry on disk. AC#3: <script>.toml beside a script (no bench.toml) opens on its values and the next edit writes bench.toml, leaving the old file; unknown tables/keys round-trip; an unparseable bench.toml opens on defaults, says why, and is never written over. AC#5: static dist/ or a missing root -> red notice + 'no host' chip, nothing runs. AC#6: web README rewritten - `npm run dev -- --host`, plainly says anyone on the network can read and write the root with no auth, mDNS names go in allowedHosts; DESIGN.md's localStorage lines updated. AC#7: dropped STL written into the project via outbox.sendThrough; same-name different-file is not overwritten ('not kept').

Fixed a race in task-52's test_a_write_the_host_refuses_as_moved_is_reported_and_not_retried (it failed on main: host file changed before boot read). e2e pages now each get their own vite preview over their own tmp root; tools.qa uses a tmp root too.

Left for later: tools.build --project still reads <script>.toml while the app writes bench.toml -> task-50 must fix (for now a CLI run of an app-saved project uses script defaults). The route cannot rename/delete a directory, so a renamed/deleted project leaves an empty dir and a dropped STL survives its project's delete -> task-48. Boot reads every project under the root.

Reviewed on main: adoption prompt and no-host screenshots, README network wording; reran tests/e2e/test_project_directory.py + test_host_store.py (18 passed). Agent's gate: vitest 310, pytest 914+1 skip x2, e2e 100, mypy 99 files.
<!-- SECTION:NOTES:END -->
