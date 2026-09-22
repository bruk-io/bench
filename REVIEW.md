# Review - five independent passes, 2026-09-12

Five reviewers (opus: geometry, dialect/architecture, browser app; sonnet: test
suite, first-time maker), read-only, each with probe scripts. Findings below
are consolidated and ranked; each carries the reviewer's file:line and a fix.
Status 2026-09-13: batches A-D applied (commits `batch A` to `batch D`); items 26, 35 and 37 remain deferred.

## Blocks cutting correct parts

1. **`bbox` is wrong for arcs in a rotated frame** (`ops.py:772-786`). Arc and
   circle extremes are sampled at quarter turns of the curve's own frame, so
   any shape with an arc rotated by a non-multiple of pi/2, or mirrored across
   a skew axis, gets a too-small box (2.35 mm off on ordinary shapes). `nest`
   sizes blanks from `bbox`, so rotated round parts overlap on the sheet and
   can run off the stock with no warning; `part_svg` clips them. Fix: compute
   extremes against world axes (project world X/Y into the frame and include
   those angles when inside the sweep).
2. **`nest` silently drops a part that is too tall upright but fits turned**
   (`nest.py:216-220`, `196-197`). `_choose` only tries the quarter turn when
   the part does not fit across; too-tall-but-fits-across returns None and
   `_pack` `continue`s. Contradicts the module's own promise. Fix: try the
   turn on either failure; make an unplaceable blank a warning, never a
   `continue`.
3. **A full-turn `Arc` exports as nothing** (`export.py:183-193`). One SVG `A`
   with coincident endpoints is omitted by the spec; the model says the hole
   is there, the cut file does not. Fix: split sweeps >= 2pi (and any > pi)
   into halves like `_circle_commands`; reject > 2pi.
4. **A param edit is discarded when a run returns mid-debounce**
   (`web/src/params.ts:76` vs `main.ts:181`). The panel's private override
   table is overwritten by main's stale copy; the widget shows 7, the cut
   files are for 4, no error. Reproduced. Fix: one owner for overrides (merge
   on `show`, or have the panel report the full table).
5. **`polygon()`/`wire()` accept self-intersecting outlines silently** (maker
   review, item 4). A bowtie strip ran `ok: True` with no warning and only
   showed when rendered. Fix: a self-intersection check in the constructor
   (segment sweep is enough at these sizes), raising or at least warning.

## Wrong but recoverable

6. **A runaway script bricks the tab** (`worker.ts:110-129`, `bridge.ts`).
   `while True: pass` hangs the worker forever, the source is persisted, and a
   reload replays it; the UI reads as "booting". Fix: watchdog + `terminate()`
   + fresh worker + a Stop button.
7. **Boot failure and worker crash show nothing** (`worker.ts:88-108`,
   `main.ts:136-149`, `bridge.ts:22`). `loadPyodide` hangs rather than
   rejects on a bad wasm; no `error`/`messageerror` listener; a failed boot is
   memoised forever. Fix: timeout the boot, listen for worker errors, clear
   the memo on rejection, and surface all three in the error panel.
8. **`contains` flattens arcs at a fixed angular step** (`ops.py:835`): error
   grows with radius (2.4 mm on a 500 mm hole). Fix: radius-driven step as
   `export._arc_step` already does.
9. **`offset` raises two undocumented `ValueError`s** (`ops.py:259-267`)
   including an opaque "zero vector" for a non-XY wire. Fix: `Raises:` block
   and a clear rejection of non-XY planes.
10. **No pinch zoom on touch** (`styles.css:301`, `viewer.ts:236`): the
    browser's pinch is suppressed and no two-finger handler exists, so a phone
    cannot zoom except Fit. Fix: two-pointer pinch about the midpoint, plus
    +/- buttons.
11. **`Ctrl/Cmd+Shift+I` is DevTools** on Chrome/Edge/Firefox outside
    headless; the advertised shortcut does not work for most users. Fix:
    `Mod-Shift-R` or `Mod-I`.
12. **Ref labels under parts are illegible** (`viewer.ts:162-166`): font size
    in model mm scales with the camera. Fix: fixed-pixel labels.

## Dialect and architecture (opus)

13. `script._Recorder` is `frozen=True` with every field a mutated container;
    `shown` is a list whose invariant is "at most one" (`script.py:191-203`).
    Fix: unfrozen notebook, `shown: _Show | None`.
14. `Process` crosses the wire as JSON but is a plain `Enum` (`model.py:20`).
    Fix: `StrEnum`, and type `PartView.process` as it.
15. `cabinet_from(**parameters: Any)` is the only `Any`, on the most
    user-facing function; the example does not use it. Fix: delete it.
16. `param`/`show` are bound through a `ContextVar` global only because
    `bench.__all__` exports them and `from bench import *` would clobber
    per-run closures (`script.py:205`). Fix: drop them from the barrel, inject
    per-run closures into the namespace; `_active` disappears.
17. `nest -> export` is the wrong direction: `Placement` pre-renders SVG path
    strings (`nest.py:41-42`) and `sheet_dxf` re-parses those strings
    (`export.py:390-426`). Fix: `Placement` carries the placed `Part`;
    `export` renders SVG and DXF from topology; the declared cycle in
    `[tool.pypeeker]` goes away.
18. `script -> library.gridfinity` should not exist (`script.py:347`): the
    runtime injects one library by name. Fix: scripts import it, or `run`
    takes an `extras` mapping.
19. `Text` sits on the topology ladder but `moved` cannot move it, so nest and
    export each carry a private special case. Fix: move `Text` to `model.py`
    (or teach `moved` the `Engraving` union) and merge the two seven-line
    helpers.
20. `Label` documents "no `/`" and enforces it nowhere (`topology.py:19`).
    Fix: a `label()` constructor that raises, used by the public entry
    points, which then accept `str`.
21. Sibling face builders disagree on argument order (`face(on, outer, ...)`
    vs `fill(w, label, on)` vs `cut(f, hole, label)`); `fill`'s `w` reads as
    width. Fix: subject first, keyword-only structure, `label` last.
22. `open_box` returns five positional faces with two twins, and the cabinet
    call scrambles `w, d, h` positionally (`gridfinity.py:368`). Fix: a `Box`
    NamedTuple and keyword-only dimensions.
23. `run(..., sheet=(w, h))` is a bare tuple and the knobs a maker wants
    (margin, gap) are unreachable from the app. Fix: a `Bed` NamedTuple
    passed through to `nest`.
24. `show(obj: object)` duck-types `Build` with three `getattr`s. Fix: move
    `Build` to `model.py` and make `show`'s parameter a closed union.
25. Public names with no external caller: `relabel`, `cut_list`, `labels`,
    `moved` in the barrel; missing from the barrel: `X`, `Y`, `Z`, `OkScene`,
    `ErrorScene`, `ErrorView`.
26. Pragmatism-governor candidates (not violations): the three `moved`
    overloads force 25 lines of re-matching downstream (one generic `moved[T]`
    would do); `Solid` appears in eight match arms that all decline.
27. Documentation drift: `face(...)` signature, "unless a plane is given",
    `run`'s signature and how `param` is bound, `cabinet_from`, `edges(tol)`,
    "add"/"port" wording in done sections, `Part` fields in README, the
    `ops.py` "re-exported from here" claim, and the pypeeker comment that
    contradicts its table.

## Test suite (sonnet)

28. The double run in `tools/check.py` re-collects but does not re-import:
    `sys.modules['bench.script']` is the same object across both runs. It
    catches dirty module globals (the thing that matters here) but not
    import-time state. Fix: pop `bench.*` from `sys.modules` between runs, or
    reword the docstring to the narrower guarantee.
29. The no-doubles guard has blind spots: bare `import unittest` then
    `unittest.mock.patch`, `pytest.MonkeyPatch()` constructed directly,
    `importlib.import_module`, and helper modules not named `test_*` are all
    invisible. Fix: scan every `*.py` under tests, ban bare `unittest`, and
    document it as a tripwire, not a proof.
30. Untested public behaviour: `angle`, `inverse`'s singular raise,
    `curve_start/end/length` directly, `wire(())`, coincident polygon points,
    `show()` outside a run, `show` of a raw `Assembly` / empty sequence /
    non-Part, `_build`'s bad-quantities raise, `_as_bool`'s "maybe", and
    `partition(target <= 0)`.
31. Flakiness: `_free_port` TOCTOU with `--strictPort`; a fixed 400 ms wait
    before the narrow-layout assertion; e2e tests share one page in file order
    so a mid-file failure cascades; mtime-based rebuild detection.
32. Hygiene: `_panel()` duplicated byte-for-byte across two files; a unit test
    in joints reaching for `model.part` as an assertion mechanism; two golden
    magic numbers without their arithmetic.

## First-hour friction (sonnet, as the maker)

33. README has no runnable example and never says `show()` nests and writes
    the sheets, that the bed defaults to 320 x 320, or that `gridfinity` is
    pre-bound in the script namespace.
34. No `line(a, b)` constructor: an engraved reference line means dropping to
    `wire((Edge(Line(...)),))`.
35. `slot()` is a stadium hole; to a woodworker a slot is a dado. No
    notch/dado/half-lap primitive; `jagged_edge` can do it but its sign
    convention is undocumented outside finger joints.
36. No `text_width(text, size)`; the estimate is a private constant in
    gridfinity.
37. No assembled view, so an interlocking joint (cross-lap dividers) cannot be
    checked in the tool - a known limit, but it bites on the first non-box
    part.

## What the reviewers said to keep

The corner-ownership property test and the DXF-readback area test are the bar
for new tests. The app's security posture (no `innerHTML`, `CSS.escape`,
`JSON.stringify` for inserted refs, MIME allowlist) and the worker protocol
(monotone ids, collapse-to-latest, stale-answer filter) are correct and were
attacked without success. The dialect is held unusually well: no mutable
defaults, no bare-name captures, one `Any`, no I/O outside `script.py`.
Performance is a non-issue: 1 ms renders, 0.5 s round trips.

## Proposed fix batches

- **Batch A (opus, core correctness):** items 1, 2, 3, 5, 8, 9, plus the
  missing tests in 30 that cover them.
- **Batch B (opus, app):** items 4, 6, 7, 10, 11, 12, and the Scene predicate
  at the worker boundary.
- **Batch C (opus, dialect/architecture):** items 13-25 and 27; 17 and 16 are
  the two that change structure and should go first.
- **Batch D (sonnet, tests and docs):** items 28, 29, 31, 32, 33, 34, 36, and
  a second example script (a plain box with a hole and engraving).
- **Deferred, needs a decision:** 26 (`Solid`), 35 (a joinery vocabulary
  beyond finger joints), 37 (an assembled view).
