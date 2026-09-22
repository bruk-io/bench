---
id: decision-6
title: An assembly is a scene, not a part
date: '2026-09-22 15:30'
status: proposed
---

# Proposal - an assembly is a scene, not a part

task-29. bench has `part()` and a stage that lays parts out for the 3D view; it has no way
to say how parts sit together. task-27 built one hinge stack of twelve bodies and every
awkward thing about it came from that one absence.

## Why

`posed()` in `examples/fulcrum_hinge.py` already does the right thing to a body -
`move(rotate(body, turn, about=AXIS), Vector(at.x, y, at.z))` - ordinary `Transform`
composition on ordinary geometry, nothing missing at that layer. The trouble starts once
the twelve posed bodies need to be looked at together.

`stage.layout()`, its own docstring says, is "where a scene's bodies stand in the 3D
view" - a viewer convenience, nothing more. It has no connection to manufacture: `nest.py`
computes a laser part's sheet position from scratch, independently, and states outright
that a printed part "is not one of its parts at all - it is passed over in silence."
`three_mf()` writes each object's mesh exactly as given, `<item>` with no transform, so does
`stl()`. Nothing that gets cut or printed has ever gone through `stage.layout()`; it exists
so that a scene of unrelated bodies - a cabinet's distinct panels, say - does not pile up on
the origin when nobody has told it how they relate. For an assembly, that is exactly the
wrong thing to do: `stage.layout()` wraps bounding boxes into rows, oblivious to where in
space the script put each body, and twelve rows of individually-correct, individually
printable bodies laid out this way is not a picture of a hinge.

So task-27 fused all twelve into a thirteenth body, wrapped it in a `Part` labelled
`"stack-posed"`, and pushed it into the same `Assembly.parts` tuple as the real twelve, with
a docstring disclaiming it - "a view and not a print" - because nothing else in the
vocabulary says "this one is for looking at, not for cutting." Nothing enforces that
disclaimer: `stack-posed` rides through export, the cut list and the quantities table
exactly as if it were a real thirteenth part, unless a maker remembers to notice its name.

The clearance check has the matching problem: `for a, b in combinations(shapes, 2):
check_clearance(a, b, fit)` walks sixty-six pairs of raw `Solid`s by hand, because there is
no call that takes "this assembly" and means "every pair in it, or the pairs I name."

Both gaps trace to the same fact, and `DESIGN.md` already says it under its own known
limits: *"there is still no assembled view - a `Build` is a cut list, not an arrangement in
space, and `Placed.on` is carried but never used to pose anything."* `Placed.on: Plane`
exists, is constructed everywhere a `Part` is (always as `XY`), and is read nowhere -
`grep` finds it touched only by one test asserting it equals `XY`. It has never been spent
on anything.

## The shape

**A placement is derived, not held.** decision-4's mesh reference is data a maker measured
by hand off a file bench cannot compute - it has nowhere to live but the project TOML.
A part's pose in an assembly is the opposite: it is the script's own arithmetic, exactly
like every other dimension in the file - `turns[n]`, `axes[n]`, `slab_y[i]` in
`fulcrum_hinge.py` are already parameters and derived values, not facts pasted in from
outside. Nothing here is measured; all of it is computed, so nothing here belongs in a
TOML. `posed()` stays exactly what it is.

**What is missing is not a transform - it is somewhere to put the *set* of them that means
"look at this together."** The fix is additive to `Assembly`, not a new domain type:

```python
@dataclass(frozen=True, slots=True)
class Assembly:
    label: Label
    parts: tuple[Placed, ...]
    posed: bool = False
```

`posed=True` says the parts in this assembly are already sitting where the script put
them, and a viewer asked to show it draws them exactly as given - no re-layout, no
row-wrapping, no bounding-box packing. `posed=False`, the default, is every assembly that
exists today: `stage.layout()` still owns it, completely unchanged. This costs nothing at
export, because export never went through `stage.layout()` in the first place - a
`posed=True` assembly's parts export exactly as a `posed=False` assembly's do today, each
one's own baked mesh, verbatim. The task's own framing - "a part prints flat and sits posed,
and both are true" - turns out not to describe two things this proposal must keep separate;
it describes one thing (the exported part, always baked wherever the script put it) that a
second thing (the viewer's optional row-wrap) was never actually part of. `posed` only ever
touches the second.

`fulcrum_hinge.py`'s `posed=True` assembly holds the same twelve `Placed` parts it holds
today - each one still individually valid, cuttable, exportable, exactly as `Build.assembly`
already expects a `Placed` to be. `stack-posed` is deleted; nothing is fused. What a maker
sees when the viewer draws a `posed=True` assembly is the twelve real parts, together, at
the coordinates the script already computed - which is a truer picture than a fused solid
ever was, because a fused body cannot be checked, cannot report which part is which, and
loses the printable-hole geometry and hole compensation that were computed per-part.

**A check gains an assembly-shaped entry point.**

```python
def check_clearance_within(
    assembly: Assembly, least: float, *, exclude: Iterable[tuple[Label, Label]] = ()
) -> tuple[Violation, ...]:
    """Every pair of ``assembly``'s parts at least ``least`` apart, save the pairs in
    ``exclude`` - named by label, so an intentional touch is declared once here rather than
    a script arguing with `min_gap` about it. Findings are recorded exactly as
    `check_clearance` records them, one part pair per finding, so a violation still names
    which two parts it is between."""
```

This replaces `for a, b in combinations(shapes, 2): check_clearance(a, b, fit)` with one
call that reads the parts off the assembly it already built, by their existing `Part.label`
- nothing new to name, `Part` was already labelled. `check_clearance(a: Solid, b: Solid,
least)` takes loose solids because a script today usually has one before it has a `Part` to
wrap it in; `check_clearance_within` does not have that problem, because it walks
`assembly.parts`, and every `Placed` there already carries its `Part` - shape and label
together - so there is nothing to correlate after the fact the way `_recorded`'s
`subjects` tuple does today. `exclude` is the seam task-34 needs: an
explicit per-pair allowance is a narrower version of what task-34 asks for, built here
because an assembly-shaped check needs *some* way to skip a pair before task-34 designs the
richer "declared contact" it eventually wants. `exclude` is not that design; it is the
minimum this proposal cannot avoid providing once it gives checks a list of pairs to walk.

### Rejected: giving `Placed.on` the pose

`Placed.on: Plane` looks like the obvious place for this - a field that already means
"where does this part sit" and already goes unused. It is not used here, on purpose. It is
not read by `stage.layout()`, by `nest.py`, by `three_mf()` or by `stl()` - nothing in the
codebase has ever given it a meaning, which means there is no existing behaviour to confirm
what it was for, only the shape of its neighbours: it sits on `Placed`, next to `Part`,
in exactly the record `Build.assembly`'s docstring calls a cut list. That is circumstantial,
not decisive, but it is enough to not spend the field on a guess. Repurposing a dead field
for a different meaning than the one its neighbours imply is how a codebase ends up with a
field two people read two different ways. `.on` is left exactly as it is - carried, unused,
somebody else's question - and this proposal adds `posed`, a field with one job and no
history.

### Rejected: a new `Scene` type, separate from `Assembly`

`Assembly` is already generic - `label` plus a tuple of `Placed` parts, no dedup baked into
the type itself. `Build.assembly` being a cut list is a convention of how a library
constructs one, not a constraint the type enforces; `fulcrum_hinge.py` already builds one
with twelve individually-posed instances and no deduplication, because `show()`'s `Root`
never demanded either. A second type carrying the same shape - a label and a tuple of
placed parts - would exist only to be told apart from `Assembly` by name, and the whole
point of this proposal is that manufacture and assembled-view were never different data,
only different things done with the same data. One flag says which; a second type would say
it twice, once in the type system and once in a name nobody could derive from the first.

## Rules

- **Pose is computed, never stored.** No `[[placement]]` table, no matrix in the TOML for
  this. If a maker ever needs to *say* a placement rather than compute one - decision-4's
  situation, a fact from outside the script - that is decision-4's shape, not this one's,
  and nothing here should grow toward it without a task that argues for it the way task-26
  argued for decision-4.
- **`posed=True` changes how an assembly is drawn, never how it is manufactured.** Cut
  sheets, quantities and export read `Assembly.parts` exactly as they do today, regardless
  of `posed` - none of them went through `stage.layout()` to begin with. A posed assembly is
  not a new kind of output; it is the same parts, plus permission for the viewer to leave
  them where the script put them instead of wrapping them into rows.
- **A part in a posed assembly is a real part.** It has its own `Stock`/`Process`, exports
  on its own, and is checked on its own - `posed=True` never means "for looking at only,"
  the way `stack-posed` had to mean it because it was not a real part. If a maker wants a
  body in the scene purely for context - a datum, a housing that is not this project's to
  cut - that is a future question, not answered by putting a non-part into `Assembly.parts`.
- **`check_clearance_within`'s `exclude` is a stopgap, not the contact model.** It skips a
  pair; it does not say *why*, does not distinguish "these should touch" from "I have not
  gotten to this pair yet," and reports nothing if an excluded pair turns out to overlap
  rather than touch. task-34 owns getting that right. This proposal only makes sure task-34
  has an assembly and a label to hang its answer on.

## What this costs, honestly

- **A `posed=True` assembly can still look wrong and pass every check.** `min_gap` measures
  distance, not whether a mechanism can physically reach the pose it is shown in - two
  bodies can be far apart and still be a pose the mechanism could never rotate through to
  reach. Nothing here claims otherwise; task-35 is the one that checks a *range* rather than
  a picked pose, and it inherits this same limit.
- **The viewer needs a second drawing path.** Today it draws whatever `stage.layout()`
  handed it, once, one way. A `posed=True` assembly needs the viewer to skip that call
  entirely and draw `Assembly.parts` as given - a real branch in `web/`, not a data change
  alone. `web/src/viewer3d.ts` already only consumes placed vertex positions with no
  placement math of its own, so this is "call `layout()` or don't," not new geometry logic
  on the TypeScript side - but it is still a branch that has to be added and tested.
- **`check_clearance_within` is one more way to ask the same question `check_clearance`
  already answers**, and a script can still write `combinations()` by hand if it wants to.
  Nothing forces the new call; task-27's script would have to be rewritten to use it, and
  this proposal does not do that rewrite as part of landing.

## What changes

- `src/bench/model.py` - `Assembly` gains `posed: bool = False`. Nothing else in the record
  changes; `Placed` and `Build` are untouched.
- `src/bench/script.py` (or wherever `check_clearance` lives) - `check_clearance_within`,
  built on the existing `check_clearance`/`clearance_between`/`_recorded` machinery, nothing
  new underneath it.
- `web/` - the viewer gains the branch: `posed` assemblies are drawn as given, everything
  else goes through `stage.layout()` exactly as today. This is the one place real design
  work remains - what "draw them as given" means for camera framing, since a posed assembly
  has no wrapped-row bounds to fit a view to.
- `examples/fulcrum_hinge.py` - `stack-posed` and its union are deleted; the twelve real
  parts are wrapped in `Assembly(..., posed=True)`; the sixty-six hand-written
  `check_clearance` calls become one `check_clearance_within` call, with `exclude=()` since
  task-27 declared no intentional contact - it buried geometry instead, which is exactly the
  distortion task-34 exists to remove once it lands.

## Sequencing

1. `Assembly.posed` and `check_clearance_within`, in `src/bench`. Provable without touching
   `web/`: a script can build a `posed=True` assembly and call the new check today; nothing
   draws it differently yet, but the data and the check are real and testable on their own.
2. The viewer's branch: a `posed=True` assembly is drawn as given, not laid out. This is
   where `fulcrum_hinge.py` actually gets looked at as a mechanism for the first time.
3. `fulcrum_hinge.py` itself: delete `stack-posed`, adopt `posed=True` and
   `check_clearance_within`. Proves the shape on the part that motivated it.

Steps 1 and 3 do not need step 2 to be reviewed on their own merits; step 2 is the one that
needs a maker to actually look at the result and say whether "drawn as given" is enough of
an assembled view or wants more (an explicit camera, an exploded offset, anything else this
proposal is not claiming).

### Not in step one, deliberately

- Any placement said by name or held as data - a placement here is always the script's own
  arithmetic.
- A richer contact model than `exclude`. That is task-34's proposal to write, once this one
  gives it an assembly and labelled parts to write it against.
- Sweeping a posed assembly across a parameter range. That is task-35's, and it depends on
  both this proposal and task-34's landing first, in that order.
- Exporting a posed assembly as one object - a 3MF, an STL of the whole scene. `three_mf()`
  already writes one object per part, each with its own baked mesh and no repositioning -
  that is not this proposal's doing and does not need to become one, and a `posed=True`
  export would still just be that, unchanged. A posed assembly is a view, full stop, until a
  task argues otherwise.
- Exploded or animated views, a camera that frames a posed assembly well, any interaction
  beyond "here is where the script put them." The viewer branch in step 2 is the minimum
  that makes a posed assembly visible at all.

## Still the owner's call

- **What does the viewer frame the camera to, for a `posed=True` assembly with no
  wrapped-row bounds to fit?** The union of every part's bounds is the obvious answer and is
  not obviously the right one for a tall, thin mechanism.
- **Does `check_clearance_within` default to every pair, or does a script have to ask for
  that explicitly?** Sixty-six pairs was cheap for twelve bodies; it will not stay cheap
  forever, and "every pair unless excluded" bakes in an assumption about assembly size this
  proposal has not tested against a bigger one.
- **Should `Placed.on` ever be reclaimed for manufacture bed placement**, now that this
  proposal has deliberately not touched it? It is still dead. This proposal's position is
  only that it is not *this* proposal's field to spend.
