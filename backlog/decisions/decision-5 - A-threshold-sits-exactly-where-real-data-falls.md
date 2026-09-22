---
id: decision-5
title: A threshold sits exactly where real data falls
date: '2026-09-22 14:00'
status: proposed
---

# Proposal - a threshold sits exactly where real data falls

task-28. Three incidents, found on three different real parts, in three different modules,
each patched by hand. Named because a fourth would be the same shape again, and the pattern
is worth deciding about once.

## The three cases

**task-20 - the survey's default heights.** Section heights defaulted to multiples of h/6.
Real parts are modelled at round numbers, so a default landed exactly on the part's own
vertex layer: a plane ran along a face instead of cutting through it and left zero-area runs
- 36 on the systainer foot, 30 and 11 on the handle. Fixed at the source: a default height
within `ROUND` of a vertex layer is nudged past it, keyed off the mesh's own layers rather
than off "a flat", which the first diagnosis guessed wrong.

**task-22, and task-24 before it - the sliver rule.** The thinnest-wall reading used to
decide "is this a wall or a sliver of the tessellation" by a band's *share* of the surface,
under 1% reading as "one place, not a wall". The base plate's four socket floors are 44.8 mm2
at 0.500 mm - a real thin floor a maker must know about - and are a small enough share of a
large part to fall under 1%, so a genuine measurement was dismissed as a tessellation
artefact. `_thinnest` in `src/bench/report.py` now decides that question by `LEAST` (one
square millimetre, absolute), and keeps a proportional figure, `_TAIL`, only to choose how a
reading already known to be real is *described* - "a thin place of that area" versus "in the
band that carries the surface" - never to decide whether it is real.

**task-23 - `_FILLET_TURN`.** A concave partial round's turn decides whether the report offers
a fillet, declines to guess, or offers a bore something has opened into, against two
thresholds: `_FILLET_TURN` (a half turn, 180 degrees) and `_BORE_TURN` (270 degrees, argued
from the handle's own 345-degree bore missing 15). Two real pieces on the handle both *print*
as "180 degrees" after `_deg`'s fixed-place rounding but sit on opposite sides of
`_FILLET_TURN`, because their true turns differ by a sub-degree amount the printed figure does
not carry: one line reads the fillet candidate, its neighbour reads "no candidate", and two
adjacent lines disagreeing reads as a bug even though each is correct for what it measured.
Not fixed - disclosed, in task-23's own notes but until this proposal not in the code. See
below.

## What the three have in common

A threshold was chosen from a figure that looks natural on its own terms - a half turn, one
percent, h/6 - and real parts are drawn at exactly those figures, because the people who
modelled them also like round numbers. The boundary was never argued from what a real part's
measurements do near it; it was read off a figure that sounds right, and the densest part of
the data is exactly where a natural figure sits. The survey's own tolerances - `ROUND`,
`SAME`, `PLACE`, `CHORD`, `TURN`, and `_DRIFT` in this module - do not have this problem,
because each one was argued from a measured distribution before it was fixed: `_DRIFT` from
the touching-pair radius-difference histogram on the real handle and base plate (no clean gap,
so the figure taken is the survey's own coarse-fit slack, twice `CHORD`), `_BORE_TURN` from
the handle's own two 345-degree bores. A threshold argued this way can still sit near real
data - `_BORE_TURN` does, 270 is not a special number - but it sits there because the data put
it there, not because it reads well.

## The rule

A new threshold in this codebase must satisfy one of two things before it is added:

1. **It is argued from a real part's measured distribution** - a histogram, a worst case, a
   real measurement that must clear it - the way `_DRIFT`, `_BORE_TURN`, `ROUND`'s nudge and
   `LEAST` all are. "It looks like a natural figure" is not an argument; "no real measurement
   on the parts this project has falls within X of it, and here is the nearest one" is.

2. **Where the threshold decides what a reading *is*, rather than how it is *shown*, it is an
   absolute figure over the printed unit (millimetres, square millimetres, whole pieces),
   never a share, a percentage or a round fraction of anything else.** A share may still
   decide *how* an already-real reading is described - `_TAIL` deciding whether a wall band
   gets its own line or is summed into a tail is fine, because by the time `_TAIL` is read the
   reading has already cleared `LEAST` and is known to be real. A share must never be the
   gate that decides real-versus-artefact, because a share moves with the size of the part and
   a real small feature on a large part crosses it exactly where a genuine one sits, as the
   socket floor did.

A threshold that satisfies (1) can still land near real data, as `_BORE_TURN` does. What the
rule rules out is a threshold chosen for how it reads rather than for what the data does near
it, and a share standing in for an absolute figure where the question is "is this real."

Neither rule asks for infinite precision, and neither is meant to prevent task-23's kind of
artefact outright - see below for why that one is recorded rather than fixed.

## task-23's boundary is recorded, not fixed

`_FILLET_TURN` already satisfies the rule above: it reuses the half-turn figure the
axis-along-Z corner wording already treats as the far end of a rounded profile, and the
alternative task-23 tried - collapsing `_FILLET_TURN` and `_BORE_TURN` into one cutover - was
rejected on the handle's own data, because a genuine 180-degree lip fillet and a genuine
270-degree bore cannot both be told apart by a single number. The artefact is not that the
threshold sits on a natural figure; `_deg` prints to whole degrees and two real turns that
differ by less than a degree can print identically while landing on opposite sides of any
threshold at all, wherever it sits. Widening `_deg`'s precision would show the split, but it
changes every degree reading in the report - not something to do without a task and a gate run
of its own - and no alternative figure for `_FILLET_TURN` survived task-23's own search of the
handle's data. So this is recorded as accepted with reason rather than resolved:
`_FILLET_TURN`'s docstring in `src/bench/report.py` now says so directly, next to the
threshold, rather than only in task-23's closed notes where the next reader of the code will
not see it.

## What changes

- `src/bench/report.py` - a new docstring section, "A threshold sits where real data falls",
  in the module docstring, naming the three cases in one place and pointing at this document.
  This is where the next person adding a threshold in this module will actually read it,
  which a document nothing links to would not achieve.
- `_FILLET_TURN`'s docstring - one sentence recording the display-precision artefact at its
  boundary as accepted, not silently missing from the code the way it was.
- No threshold value changes. `LEAST`, `_TAIL`, `_DRIFT`, `_FILLET_TURN`, `_BORE_TURN`,
  `ROUND` and the survey's height nudge are exactly what they were; this task is a decision
  about the next one, not a retuning of these three, and none of the three is argued from a
  distribution this task went and measured - the arguments cited above are the ones already in
  the code and in task-22's and task-23's own notes.
- `backlog/tasks/task-28` - acceptance criteria checked off against this document.
