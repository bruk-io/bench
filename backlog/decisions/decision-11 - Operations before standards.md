---
id: decision-11
title: Operations before standards - what bench builds in
date: '2026-09-24 03:00'
status: accepted
---

# Operations before standards - what bench builds in

Asked 2026-09-24, with no project in mind: which built-ins are worth shipping, the way
Gridfinity already is? Answered from what one real design - the wall vent (projects/vent,
2026-09-23) - had to build by hand.

## Two kinds of built-in

**Operations** are verbs every design reaches for: hollow a body, bend a duct, cut a thread,
round a corner. **Standards libraries** are ecosystems with published dimensions a part must
match: Gridfinity, a 4 inch dust hose, a Raspberry Pi's holes, Multiboard's grid.

The vent needed no standard beyond Gridfinity's kind of thinking, but it missed six operations,
and it rebuilt two of them twice. A library built on missing operations re-invents them the same
way. So **operations first; libraries on top of them.**

## The operations, and what the modeller allows

The browser's modeller (Manifold, `web/src/modeller.ts`) offers bench: `section`, `extrude`
(height only), `revolve`, `transform`, `union`/`difference`/`intersection`, `hull`, `imported`
(a solid from any triangle mesh), and `mesh`/`volume`/`min_gap`. What each operation needs:

| Operation | The vent's workaround | Feasibility |
|---|---|---|
| **Orientation-aware `check_fits`** | rotated each part onto the bed by hand before checking | Python only; task-64 already lays exports down by `Orient` |
| **Imperial fasteners** (#6/#8 wood and drywall screws, 1/4-20) | used M4 for a #6 drywall screw | data in `fasteners.py` |
| **`shell(body, wall, open=...)`** | an outer and an inner loft subtracted, twice (funnel, hopper) | recipe-level: re-run the body's own extrude/revolve/loft/hull on the profile inset by `offset`, and subtract - no kernel change. A tapered or hulled body gets a wall measured in the profile's plane, not normal to the surface; say so |
| **Rounded and chamfered profiles; eased rims** | 45 degrees built into the hood and hopper by construction | 2D fillet/chamfer of a wire's corners before extruding (offset out and back in); an extrusion's top or bottom rim eased by a hull of slices, generalising `library/print.eased()` |
| **Threads** (printed screw threads, jar and cap threads) | none | Manifold's own extrude takes a twist and a top scale; bench's binding drops them. Expose them, then a thread is the standard twisted-extrusion of an offset circle |
| **Sweep along a path** | a 90 degree bend faked with `revolve`; no S-bend or offset possible | no kernel sweep. Two routes to compare before choosing: a chain of hulls between successive profile slices (convex profiles only - circles and rectangles, which is every duct and pipe), or a mesh computed in Python and built with `imported` (any profile, but a hull or an import names no faces) |

**Not offered: fillets on arbitrary 3D edges.** A mesh kernel has no edges to round; bench's own
docs already say so (`report.py`, `solids.hull`). Rounded profiles and eased rims cover what a
printed part mostly wants; a true edge fillet is not promised.

## Order

Small and certain first, then the two the vent rebuilt twice, then the kernel-touching ones:

1. Orientation-aware `check_fits`, and imperial fasteners.
2. `shell`.
3. Rounded/chamfered profiles and eased rims.
4. Threads (exposes twist in the modeller binding).
5. Sweep - a short comparison of the two routes first, then the one that wins.

Each ships the way everything here does: pure Python where it can be, tested against the
modeller the app ships, an example the gate runs, and the checks that make it safe (a shell's
wall against the printer's minimum, a thread's clearance from the fit table).

## Then the standards libraries

Chosen by one rule: **a published spec, a real community, and a fit that goes wrong if you
guess.** In likely order, each a `Spec` and functions like `library/gridfinity3d`:

- **`ducts`** - hose and duct sizes, spigots and sockets at the fit table's slide, reducers,
  branches, elbows, square-to-round transitions, blast gates. Built on `shell` and sweep; the
  vent's `manifold.py` becomes a few calls.
- **`enclosures`** - Raspberry Pi / Arduino / ESP32 and PCB hole patterns and standoffs, DIN
  rail (TS35) clips, cable glands, keystone jacks, 10 and 19 inch rack panels. Built on `shell`
  and `fasteners`.
- **`flexures`** - snap latches with the strain and release-force maths the vent derived by
  hand, annular snaps, living hinges, checked against each filament's strain limit (a strain
  limit joins `print.Material`).
- Then: **`multiboard` / openGrid**, **`skadis` / pegboard**, **`cleat`**, **`systainer`**
  (promoted from its example), **`gears`**, **`bearings`**, and laser joints beyond fingers.

These are not filed yet - each wants its own decision when its turn comes, the way Gridfinity
had one.
