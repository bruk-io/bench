---
id: task-18
title: 'A project is a script and its values, not a script alone'
status: Done
assignee: []
created_date: '2026-09-22 21:04'
updated_date: '2026-09-22 02:05'
labels:
  - feature
  - project
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The values a maker arrives at by turning knobs live in localStorage, as part of a kept file - name, source, overrides. So they are not versioned, not shareable, not visible, and gone if the browser's storage is cleared while the script survives in the repository.

The split between what a thing is and which one you are building already exists in the code. One half is a first-class file and the other is a hidden string in a browser. This promotes the half that is hiding: a values table in a TOML beside the script, which the dataclass still declares and still provides the fallback for.

It is smaller than it sounds. configured(cls, values) already takes an untrusted mapping - the panel's table, JSON off a wire - and a TOML table is that mapping. tomllib is standard library at bench's floor, so src/bench does not change and no dependency is added. The script never reads the file: that is I/O, and it belongs at the edge with extras, reference and the kernel.

The reasoning, the rules, the costs and the open questions are decision-3.

Reverse-engineering measurements (task-14) want the same home for the same reason, as a second table rather than as more parameters - but that waits until there is something to put in it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A script can be run from a file with its values beside it, and the run uses them
- [x] #2 A script with no file beside it behaves exactly as it does today
- [x] #3 The dataclass declares and provides the fallback; the file says which instance is being built, and a field absent from the file keeps its default
- [x] #4 A value the file holds that its field cannot read is refused by name, as it is from the panel
- [x] #5 No new runtime dependency, and nothing under src/bench changes to support it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Every criterion here is met by 18.1, merged as #18: a script runs from a path with a TOML beside it, a script without one runs on its defaults, the dataclass declares and the file says which instance, a value a field cannot read is refused by name, and nothing under src/bench changed with no dependency added.

The parent stays In Progress anyway, because 18.2 is open and it is the half a maker actually touches. Today the values file only helps at a command line; in the app the values are still a JSON blob in localStorage. The criteria written here were about the run, and they are honestly met - but closing the parent would say the idea has landed, and for anyone using the browser it has not.

Closed once 18.2 merged as 17c82f5 (PR #21). The note above said the parent would stay open until the half a maker actually touches had landed - in the app the values were still a JSON blob in localStorage. They are not any more: the kept record is `{ name, source, values }` with the values as TOML, readable as a tab, carried by duplicate and rename, and downloadable as the script-plus-.toml pair that `tools.build` runs without a browser. Both halves of decision-3's steps 1-4 are now in.

Step 5 ([[measured]]) is deliberately not part of this and waits on task-14 having measurements worth writing down - which, with task-14.2's survey work in flight, is now close. decision-3 stays 'proposed' rather than 'accepted': three of its questions were answered by implementation (write on every edit, write back as built, and the TOML as a rendering rather than a document the maker owns) and those answers deserve the owner's eye before the decision is marked accepted.
<!-- SECTION:NOTES:END -->
