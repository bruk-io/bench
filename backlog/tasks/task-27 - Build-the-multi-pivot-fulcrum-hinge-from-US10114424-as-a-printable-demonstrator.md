---
id: task-27
title: >-
  Build the multi-pivot fulcrum hinge from US10114424 as a printable
  demonstrator
status: Done
assignee: []
created_date: '2026-09-22 21:05'
updated_date: '2026-09-22 21:49'
labels:
  - feature
  - example
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A new example: one hinge stack of the sequential multi-pivot hinge disclosed in US 10,114,424 B2 ("Multi-Pivot Hinge", Microsoft, granted Oct 2018, continuation of an application filed Nov 2014; inventors Campbell, Bitz, Tazbaz). This is the Surface Book hinge - the patent itself uses the owner's word for it once, saying the unrolling action "can move the device fulcrum backwards providing a longer wheel base".

The source is the patent itself, US 10,114,424 B2 (18 pages), from the USPTO or Google Patents.

**This is NOT the survey path, and the distinction matters.** The patent contains no dimensions at all - not one millimetre, no radii, and no angles beyond "obtuse" and "90 to 180 degrees". Patent figures are not to scale by convention and this one offers nothing to anchor them to. So there is nothing to measure and `survey`/`report` do not apply. What the patent gives is a topology and an interlock rule, precisely described; the numbers are ours to choose and must be recorded as OUR choices, driven by printability, never presented as the patent's.

**The mechanism, from the description.** A hinge stack is a chain: a second-portion element (keyboard side) carrying a terminus, several radially arranged links, and a first-portion element (display side). Four keyed shafts define four pivot axes. Each link is an offset shape the patent likens to a lightning bolt - a first region and a second region joined by a central region - with two parallel bores: one CIRCULAR passageway and one D-PROFILE passageway. A shaft is therefore keyed to one link and free to turn in its neighbour, which is the drive train. Sequencing pins ride in channels cut by four cam surfaces per link (two partially defining the channel's fore-aft freedom, two controlling rotation), plus cam surfaces on the terminus and on the first-portion element. A pin blocks rotation about the next axis until the current link has swung its allowed travel, at which point the cam surfaces align, the pin slides in the negative x direction, and the next axis unlocks. Opening unrolls from the keyboard outward; closing rolls up from the display inward - that asymmetry is claim 1. Rotation limiters cap each axis's travel.

**Why bench fits the parts well.** Every axis is parallel and every cam surface lies in the link's 2D profile: it is a planar linkage extruded, with no lofts, hulls or spline surfaces needed. The cams ARE the outline, which is what `rect`/`circle`/`fill`/`extrude` is for. `examples/hinge.py` already has the directly reusable precedents - `clearance(Fit.SLIDE, PLA)` for turning fits, `hole(printed=...)` for what a printed bore takes back, and `eased()` for a rim chamfer on a kernel with no chamfer verb. Read it first.

**Why bench cannot finish the job, and this must be said in the script rather than discovered.** bench models static geometry. There are no joints, no constraints and no motion, so nothing here can verify that the cam sequencing actually works - and that interlock is the whole invention. The script can build the parts, pose the stack, and check that a given pose does not interfere (`min_gap`), and it can parameterise a deployment that drives the per-axis angles in the patent's order so the three positions of FIG. 9 can be stepped through. It cannot prove the pins lock and release in sequence. Deriving functional cam profiles from prose with no dimensions is real mechanism design and should be expected to need physical iteration.

**Decisions already taken by the owner:** a printable demonstrator at roughly 2.5-3x device scale (at device scale the sequencing pins are on the order of 1.5-2 mm sliding in channels - machined metal territory, not FDM), and ONE hinge stack rather than the five-stack assembly with covers of FIG. 7. Note that scale is not a clean multiplier: clearances and minimum walls do not scale with it, so a single scale knob would quietly lie about the fits. Parameterise the sizes that matter and let the fits come from the print library.

Scope note: this draws and poses a mechanism. It does not claim to reproduce a product. The patent is in force (term runs to about Nov 2034) and all three independent claims are to "a computing device comprising", not to a hinge alone - worth knowing before this became anything more than a study.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 One hinge stack builds as parts: the links, four keyed shafts, three sequencing pins, and both end elements with their cam surfaces
- [x] #2 Each link has one circular bore and one D-profile bore, so a shaft is keyed to one link and free to turn in its neighbour - the patent's drive train, not a pair of plain holes
- [x] #3 A deployment parameter poses the stack by driving the per-axis angles in the patent's sequence, and the posed stack is checked for interference rather than assumed clear
- [x] #4 Every dimension is the script's own choice made for printability, recorded as such, with the fits taken from the print library rather than invented
- [x] #5 The script states plainly what is not verified: the cam sequencing interlock is geometry here, and no check in bench proves it locks and releases in order
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read the patent (FIGS. 8, 8A, 9, 10; columns 3-6) and trust it over the brief where they differ.
2. Derive the interlock as arithmetic: ring gap narrower than a pin diameter (a pin can never rest in neither pocket) and wider than a pin radius (a pocket shallower than the pin's radius ejects rather than traps), pocket depth from those, ring radius from bore + wall + depth.
3. Lay the stack out along the axis in slabs: two rings per shaft, each link's second region two slabs deep and standing on the slab below so it prints without support; each pin four slabs long, in its link's channel and reaching the pocket of the body either side.
4. Build the parts: identical links, base with terminus and lug, arm with cutout, D shafts with heads, pins; pose by one `deployment` in the patent's order; place pins fore/aft from the pose.
5. Check every pair with `min_gap` at the fit, on the real kernel, at closed, FIG. 9's positions, open, and a handover at maximum travel; overhangs on a link and a shaft.
6. Wire into the functional and adapter test layers and the README; run the gate; PR without merging.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**What the patent says where the brief differs.** (a) The shaft is D-shaped along its whole length inside the stack - FIG. 9 draws the flat in every section and column 4 says the circular passageway is simply a round hole the D turns in; built that way, not as a round shaft with a keyed length. (b) Closed is the *curled* state (FIG. 9 Position One is "analogous to the closed position of FIG. 5") and deployed is unrolled flat; opening flattens the axis nearest the second portion (keyboard) first. (c) Claim 1's asymmetry is the direction one path is walked, not two paths: a pose is one scalar. A `direction` knob was built, found to produce identical poses, and removed. (d) Column 5 calls both cam surface 822(2) and 822(4) "in the first region"; FIG. 8 puts 822(4) on the second region, and the figure was followed. (e) Position Three's prose names rotation about 504(3) while the figure shows links A-C flat; the figure was followed.

**Dimensions (all the script's own):** shaft 6 mm, flat one third of the radius deep; pin 5 mm; ring wall 2.5 mm; slab 6 mm; travel 45 deg per axis (4 x 45 = 180, display flat over keyboard). Ring gap 1.4 pin radii, pocket depth = pin diameter - gap + fit + 0.3 mm, ring radius = bore + wall + depth (+ fit + comp), so R = 8.1, pitch 19.7, pin travel 2.5 mm. Fits from `clearance(Fit.SLIDE, PLA)` and `PLA.hole_compensation`; the D bore takes both by hand because `hole` cannot draw a D. The lug's concave inner arc gets `CHORD` on top of the fit because a concave arc is meshed as chords inside its circle.

**Deviations from the patent, on purpose:** second region two slabs deep so the link prints without support (the patent's Z-link overhangs); rotation limiters built as a sector lug in a sector cutout inside the stack rather than on the shafts outside it (their form is not drawn); no far-end shaft retention.

**Checks:** every pair of the 12 bodies with `min_gap` at the fit, on the real kernel, at 11 poses/knob settings including extremes - all clear. Overhangs on a link and a shaft - clean once the head and lug were buried in their neighbours rather than coplanar with them. `check_wall` was tried on the rings and left out with the reason written in the script: each reading (0.67 mm default, 0.08 mm with a 3 mm pin) was a strip of pocket wall a few hundredths of a millimetre wide at the corner where a pocket meets the rim, and a ray from its middle leaves the ring through the corner; the walls that matter are `ring_wall` by construction and are printed instead.

**Not verified and unverifiable here:** that a pin moves between pockets when it should. The pose is consistent; the mechanism is a desk question.

**Viewer:** the stage lays bodies out in a row, so the pose is also shown fused as `stack-posed`, labelled a view and not a print.

Gate on branch fulcrum-hinge (commit 4bfc616): 781 passed twice + 1 pre-existing skip (baseline 773), 169 component, 73 e2e. PR opened against main; left In Progress for the owner to verify and merge.

Merged as 2171fae (PR #29, squashed). Branched from f0b25fa, pushed without incident, no rebase needed. Gate: 781 Python passed twice (773 baseline + 8 from the new example in the functional and adapter layers), 169 component, 73 e2e. main's tree is the gated fa2669f, and src/bench is untouched - verified by diff, not just claimed.

FOUR PLACES THE PATENT DIFFERS FROM THIS TASK'S DESCRIPTION, patent followed in each. (1) The shaft is a D along its whole length turning in a round hole - column 4 says the profile approximates a capital D and FIG. 9 draws the flat in every section - not 'circular along most of the length' as I wrote. (2) Closed is the CURLED stack (Position One is analogous to the closed position of FIG. 5); deployed is unrolled flat, extending the foot. (3) Claim 1's asymmetry is one path walked in two directions, not two families of poses: the agent built a `direction` knob, found opening-to-0.4 and closing-to-0.4 give the same stack, and removed it. (4) Column 5 calls both 822(2) and 822(4) 'in the first region' while FIG. 8 clearly puts 822(4) on the second region, and the Position Three prose names rotation about 504(3) while the figure shows links A-C flat. The figures were followed both times and the script says so.

Dimensions are all the script's own and recorded in its docstring: shaft 6 mm with the flat a third of the radius deep, pin 5 mm, ring wall 2.5 mm, slab 6 mm, 45 degrees of travel per axis so four axes give 180. The derived numbers carry their reasoning - the ring gap is 1.4 pin radii, narrower than a pin diameter so a pin can never rest in neither pocket and free two axes at once, and wider than a pin radius so the pocket stays shallower than the pin's radius and ejects it under torque rather than trapping it. Fits are clearance(Fit.SLIDE, PLA) per side with PLA.hole_compensation on every printed hole, added by hand for the D bore since hole() cannot draw a D. No scale knob, and the docstring says why.

Deviations made deliberately, all disclosed: each link's second region is two slabs deep so a link prints on its first region with nothing overhanging, where the patent's Z-link would need support; the rotation limiters are a sector lug riding in a sector cutout rather than the patent's shaft-mounted limiters, which FIGS. 5-6 do not draw in enough detail to copy - and without SOME limiter the closing sequence cannot work, since nothing would redirect torque to the next axis.

check_clearance was run on every pair of the 12 bodies at five poses and at knob extremes, on the real kernel, and found two real problems that were then fixed: coplanar faces (shaft head against its ring, lug on its ring) and chord sag on the stop lug's concave inner arc, which needed CHORD on top of the fit because a concave arc meshes as chords inside its circle - min_gap read 0.16 mm against a 0.20 ask before that.

HONEST DEVIATION ON check_wall, which the task asked for and did not get. It was left out with its readings written into the script: it read 0.67 mm on defaults and 0.08 mm with a 3 mm pin, each from a strip of pocket wall a few hundredths wide where a pocket's last chord meets the rim's, the ray leaving the ring through the corner. ring_wall=4 'passed' only because the strip landed elsewhere - so passing was luck, and relying on it would have been worse than omitting it. This is the same sliver-artefact behaviour task-14.2 found on real exports, where walls.thinnest lands on a 0.001-0.05 mm artefact while the bands carry the real answer. The real walls are ring_wall by construction and are printed on stdout.

What the agent believes would work if printed: the parts fit: shafts key in the D bores and turn in the round ones, pins sit in their channels and pockets, rings clear each other and the pins they pass, lugs sit in their cutouts, and closed and open are locked by a pin in one pocket at every pose. All measured geometry. What is unverified, and it is the invention: that a pin actually TRANSLATES from one pocket to the other at a handover. The arithmetic says it should, the pocket being shallower than the pin radius so contact normals have an outward component, but no check in bench measures force or motion and 0.2 mm printed fits with 2.5 mm of travel may bind. The stop lugs take the closing torque and their strength is unmeasured. Expect physical iteration on pocket depth and pin diameter.
<!-- SECTION:NOTES:END -->
