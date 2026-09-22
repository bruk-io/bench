---
id: task-18.1
title: 'Run a script from a file, with its values beside it'
status: Done
assignee: []
created_date: '2026-09-22 21:05'
updated_date: '2026-09-22 21:11'
labels:
  - tools
  - project
dependencies: []
parent_task_id: task-18
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while sequencing decision-3, and it changes where this starts: nothing runs a script from disk. tools/ holds check, qa, kernel_timing, preview and stack - a gate, a screenshotter, a timer, a server and a Pyodide harness. The only real hosts run() has are bench.worker, which is the browser, and the test suites.

So there is nowhere for "the host reads the values file" to live, and this makes that place: a command-line entry that takes a script, reads a TOML beside it if there is one, and hands its values to run() as the overrides argument that already exists.

Reading a file is exactly what a command-line host is for, it makes the values file useful before any browser work, and the repository is missing this anyway - there is currently no way to run a script and get its cut sheets without opening a browser.

Nothing under src/bench changes. The script never reads the file; the host does, and hands in a mapping, the way extras, reference and the kernel are all handed in.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Running a script from a path produces its scene, and says what was made and what was violated
- [x] #2 A TOML beside the script supplies the values, and a field it does not mention keeps the dataclass default
- [x] #3 A script with no file beside it runs on its defaults alone
- [x] #4 A value the file holds that its field cannot read is refused by name rather than silently dropped
- [x] #5 The files a run produces can be written out, so cut sheets are reachable without a browser
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`tools/build.py`: a script path in, a scene out, and the files written down with `--out`. The values come from a TOML beside the script, read with `tomllib` and handed to `run()` as the `overrides` argument it already takes - so nothing under `src/bench` changed and no dependency was added, which was the point of the shape.

Proved on a real example rather than a fixture. `examples/gridfinity_cabinet.toml` drives `examples/gridfinity_cabinet.py` to `14 parts on 7 sheets - 0 errors, 0 warnings`, writing sheet SVGs and DXFs, the printed baseplate's `.scad`, and per-part outlines whose names come from the labels the file supplied.

The example file also earned its keep immediately: the first version had three labels against six drawers, and the script refused it at its own line. The file's values are checked by the script's rules, not merely parsed - which is exactly criterion #4, and is covered by a test asserting the tool reports it and answers non-zero rather than pretending it built something.

Correction: those criteria were ticked on the strength of tests that were not honestly green. They pass in isolation and four of them fail inside `tools/check.py`, which runs the suite twice and drops `bench` and every `bench.*` module from `sys.modules` between the runs.

`tools/build.py` bound `run`, `binary` and the scene types at import time, and `tools` is not in the set that reset drops - so the second run handed a freshly-imported `Part` to a stale `run`, and `show`'s `match thing: case Part()` compared it against the first run's class and refused it: "cannot show 'Part'". A real defect in the tool, not a test artifact, and `_reset_bench_modules`' own docstring describes this failure mode exactly.

Fixed by importing `bench` inside the functions that use it, with the scene types behind `TYPE_CHECKING` - the same thing `tests/functional/test_examples.py` does, and for the same reason. The ticks go back on when the full gate is green rather than before.

Green now, and by the thing that caught the bug rather than in spite of it: the full `tools/check.py` passes both runs - 686 passed, up from 682 - with ruff, format and mypy clean over all 84 files. The deferred imports hold across the module reset, which is the only place the defect ever showed.

Both paths checked for real. `examples/gridfinity_cabinet.py` with its TOML: 14 parts on 7 sheets, 29 files written. `examples/hinge.py` with no file beside it: runs on its own defaults, and honestly reports three `unchecked` findings, because no kernel is loaded and "I could not tell" is not "it is fine".
<!-- SECTION:NOTES:END -->
