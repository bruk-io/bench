---
id: decision-2
title: A script's parameters as one dataclass
date: '2026-09-22 19:47'
status: accepted
---

# Proposal - a script's parameters as one dataclass

Status: steps 1-4 implemented, 2026-09-14. `param()` is gone; `params.py`, `show(build)` and
the seven examples are in. Still open, confirmed against the code on 2026-09-15: `params` on
`ErrorScene` (it still carries only `ok`, `error`, `stdout` and `stderr`), so a `build` that
raises loses the panel (see the correction under *What the runtime does*) - considered
and dropped on 2026-09-15 (task-13, archived) - and the owner's calls at the end.

## Why

`param()` works, and it has three problems that all come from the same place - a parameter
exists only once the script has run far enough to declare it.

- **The panel cannot see a parameter the script did not reach.** A script that raises before
  its `param` calls shows an empty panel, and the web app has special cases for it
  (`forgetOverridesNobodyDeclares` only prunes on a run that produced parameters).
- **The values arrive through a hidden input.** `param` is a closure over the run's notebook,
  so a script is not a function of its settings; it asks the runtime for them line by line.
- **Settings are declared twice.** `gridfinity_cabinet.py` declares eleven `param`s and then
  copies each one into `gridfinity.Spec(units_x=units_x, units_y=units_y, ...)` by hand.

And the panel's own bug on 2026-09-14 - an emptied field ran the cabinet with `units_y = 0` -
was caught in `params.ts` because the core has nowhere to check a value before it is used:
`min` and `max` are hints, "not enforced here".

## The shape

Three pieces, each doing one thing.

```python
from dataclasses import dataclass
from typing import Literal

from bench import *
from bench.library import gridfinity


@dataclass(frozen=True, slots=True, kw_only=True)
class Cabinet:
    """Every setting a person can change, and nothing else."""

    units_x: int = knob(4, min=1, max=7, label="Units across")
    units_y: int = knob(2, min=1, max=5, label="Units deep")
    height_u: int = knob(3, min=1, max=12, label="Bin height (7 mm units)")
    drawers: int = knob(6, min=1, max=10, label="Drawers")
    kerf: float = knob(0.25, min=0.0, max=1.0, step=0.01, label="Kerf")
    baseplate: bool = knob(True, label="Printed baseplate")
    labels: str = knob("", label="Drawer labels, comma separated")


def build(p: Cabinet) -> Build:
    engraved = tuple(text.strip() for text in p.labels.split(",") if text.strip())
    return gridfinity.cabinet(
        gridfinity.Spec(
            units_x=p.units_x, units_y=p.units_y, height_u=p.height_u, drawers=p.drawers,
            kerf=p.kerf, baseplate=p.baseplate, labels=engraved,
        )
    )


show(build)
```

1. **The dataclass is data.** A plain frozen dataclass - no `@params` decorator, no methods,
   no base class. `Cabinet()` is the defaults. `knob()` is `dataclasses.field` with the
   panel's hints in its `metadata`; a field with a bare default is a parameter too, just one
   with no range or label.
2. **The factory is a function in the core.** `configured(cls, values) -> P` takes the
   dataclass and an untrusted mapping - the panel's table, `run()`'s argument, a dict in a
   test - and returns a checked instance. It is where today's `_coerced` goes, and where a
   value outside `min`/`max` is held at the nearer end.
3. **The script is a function of its settings.** `build(p)` never loads anything. The script
   ends with `show(build)`, and the runtime reads `p`'s annotation to find the dataclass.

The host is one line: `build(configured(Cabinet, values))`.

## Rules

- **One dataclass per script.** `build` takes exactly one parameter, annotated with a
  dataclass. Two parameters, no annotation, or an annotation that is not a dataclass is an
  error scene naming `show`'s line.
- **Flat, scalar fields.** `bool`, `int`, `float`, `str`, or `Literal[...]` of one of those,
  which becomes a menu - so `choices=` goes away and the type says it. Anything else (a
  nested dataclass, a `tuple`, `Screw`) is an error at `show`, naming the field.
- **Field names are the parameter names.** They are what the panel's override table, the
  e2e ids (`#param-units_x`) and `localStorage` key on, so porting an example keeps every
  name it has today - `drawer_labels = param("labels", ...)` becomes a field called `labels`.
- **`configured` ignores names it does not know.** A table kept from an older version of the
  script is not an error; the web app's pruning stays as it is.
- **`show(thing)` keeps its other arm.** A script with nothing to adjust shows its part
  directly and needs no class. `show` takes a `Showable` or a one-argument callable.

## What the runtime does

`run(source, overrides)` executes the script as now. When `show` is handed a function, all of
this happens inside that `show` call, while the script is still running:

1. read the dataclass off `build`'s one annotated argument, and its fields into `ParamView`s;
2. `configured(Cabinet, overrides)`, which may raise `ValueError` naming the field;
3. call `build`, and collect what it returns exactly as `show(thing)` collects a thing today.

Doing it inside the call is what keeps every line number honest with no new plumbing: a
refused setting or a `build` with no annotation is reported at the `show(build)` line, an
exception inside `build` at the build's own line, and a check called inside `build` records
its line because `_asking_line` walks out to the first frame compiled as `<script>`.

**Correction, found while implementing.** An earlier draft said a `build` that raises still
fills the panel. It does not: `ErrorScene` has no `params`, so a failed run carries no
declarations whatever the script did, exactly as today. The fields *are* read before `build`
is called, so the fix is only a contract change - `params` on `ErrorScene`, mirrored in
`web/src/scene.ts` - and it is left for its own step.

`ParamView` and the scene do not change, so the web app does not have to. `params.ts` keeps
its field-level checks - they are what stops a half-typed number from running at all - and
the core becomes the thing that is right when a caller is not the panel.

## Where it lives

A new `src/bench/params.py`: `knob`, `declared(cls) -> list[ParamView]`, and `configured`.
It imports nothing from `script.py`. `knob` is exported from `bench`, because unlike `param`
it touches no run's notebook and does not need to be injected. `script.py` loses `param`,
`_declared` and `_coerced`, and `show` gains its callable arm.

## What changes

- `src/bench/params.py` - new, with unit tests: coercion, ranges, `Literal` menus, unknown
  names, a non-scalar field.
- `src/bench/script.py` - `show(build)`, `param` removed, the module docstring's example.
- `examples/*.py` - all seven ported, one commit, names unchanged.
- `tests/functional/test_script.py` - the eight `param` tests rewritten against the new
  shape. One has no equivalent: *a parameter declared twice* cannot be caught, because a
  class body silently keeps the second of two same-named fields.
- `DESIGN.md` (the `script.py` section), `README.md`, `web/README.md` - the examples in them.
- `web/` - nothing required.

## Sequencing

1. `params.py` and its tests, used by nothing.
2. `show(build)` in `script.py`, with `param` still working beside it.
3. Port the seven examples; the e2e suite is the check that nothing a person sees moved.
4. Remove `param`, `_declared`, `_coerced`; update the docs.

## Still the owner's call

- **Enforce ranges in the core? Decided, 2026-09-14: clamp.** An override outside `min`/`max`
  is held at the nearer end rather than stopping the run, and the scene's `values` say what
  was built. An int held at a fractional end rounds inward so it stays inside. Two things
  still raise: a value its field cannot read at all (`""`, `"wide"`, `nan`), and a *default*
  outside its own range, which is the script contradicting itself rather than a panel
  sending something odd.
- **`Literal` for menus, or keep `knob(choices=...)`?** `Literal` is the cleaner type and
  `p.tab` then type-checks as the five words it can be; `choices=` is what people already
  know from `param`.
- **Writing a panel value back into the script.** With one class, "make this the default" is
  rewriting one `knob(...)` default in the class body. Not in this proposal; this one only
  makes it possible.
