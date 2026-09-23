---
id: decision-10
title: A fit is a face on each part and a Fit
date: '2026-09-23 16:00'
status: proposed
---

# Proposal - a fit is a face on each part and a `Fit`

Asked for while modelling a wall vent (projects/frame, 2026-09-23): "select two faces, pass
them to a fit function, which arranges the objects and shows if there are any fit issues."

## Why

The vent's attachment hooks over the frame's collar. Getting that right took three things
bench has no single word for:

- **Placing it by hand.** `attachment()` is written in the frame's own coordinates - its back
  face at `z = flange`, its groove at `collar_inset - gap` - so the two parts sit together
  only because one script drew both from the same corner. Nothing says *this face goes on
  that face*; the numbers just happen to agree.
- **Checking it by hand.** `check_clearance(collar, fitting, gap)` for the groove,
  `check_contact(plate, fitting)` for the back face, each chosen and wired by the script.
- **Showing it by hand.** `assembly(..., posed=True)`, a `fitting` knob, a pose function and
  `check_clearance_through` - and even then the part that matters, a tongue under a hook, is
  hidden inside the attachment where no view shows it.

Each piece exists; the verb that joins them does not.

## What a face already gives

`plane_of(solid, ref)` answers a full frame - origin, normal out of the material, X in the
face - and it is **the frame the face was authored in**, not one computed from triangles: the
flange's `top` has its origin at the corner the flange's profile was drawn from, X the way
that profile ran. It is deterministic and does not move when the kernel or the tessellation
does. A round face answers a tangent frame at `around=`/`along=`.

So **one face on each part is enough to place a part fully**: lay the moving face's frame on
the fixed face's frame, normals opposed. Tried against the vent: the attachment's back face
onto the flange's front face lands the attachment exactly where `attachment()` puts it by
hand - because both were drawn from the same corner.

**And that is also the catch.** Where a face's origin sits is invisible to somebody clicking
it. Had the attachment been drawn centred on its own origin, the same two clicks would put it
half its width off. Two faces are enough for the kernel; they are not always enough for the
person.

## The shape

```python
fitted = mated(frame, ref("frame/flange/top"), attachment, ref("attachment/base/bottom"),
               fit=Fit.CONTACT, offset=Vector(0, 0), spin=0.0)
```

- **`mated` moves the moving part and returns the moved body** - `topology.moved(b,
  to_world(fixed_frame) · turned_over · to_local(moving_frame))`, rigid, nothing else. The
  maths is Python (a module named for what it does, `mate.py`); the viewer only draws.
- **`fit`** says what the pair is for: `CONTACT` (touch), or a clearance `Fit` - the gap along
  the normal is `clearance(fit, material)`, so a slide fit comes out of the same table as
  every other printed fit.
- **`offset`** (in the fixed face's plane) and **`spin`** (about its normal) are the honest
  answer to "the origins don't line up": explicit, visible in the script, and zero when both
  parts were drawn the same way.
- **Round faces** are the second kind: a bore and a shaft. That pair aligns axes and sets the
  radial gap from the `Fit`; it leaves spin and slide free, so it needs `along=` and `spin=`
  or a planar pair beside it (see Open questions).

**Checking is not a separate step a script can forget.** `mated` declares the pair - contact
or clearance at the asked gap - and the assembly's other pairs are walked with
`check_clearance_within`, the mated pair excluded and declared instead. What comes back names
the measured gap against the asked one: *"attachment/groove clears frame/collar by 0.20 mm,
asked 0.20 (slide)"* or the pair and the place they foul.

**Findings must land on the parts people are looking at.** A finding reaches a part by
identity (`views._label_of`: the part whose shape *is* the object the check measured), so
the body `mated` returns is the body the part is made from - checked and shown as one object,
never a copy.

## Picking the two faces

decision-7's rule: a pick writes into the script, the app keeps no selection state. Today a
click inserts one `ref(...)`. The proposal: click a face, shift-click a face on another part,
and **Insert fit** writes the `mated(...)` line with both refs filled in. Before inserting,
the view draws both faces' frames - origin, normal, X - so the invisible origin is visible at
the moment it matters.

## Showing it

- Findings in Problems, highlighted on both parts in the view (identity, above).
- A fit that moves - put on, then dropped onto a hook - is the vent's pose knob and
  `check_clearance_through`, which `mated` should make easy rather than replace.
- A **section view** (the viewer clipping at a plane) is what shows a hidden fit. It is its
  own proposal; it is listed here because this one is where "show the user" runs out without
  it.

## Sequencing

1. **task-57 first.** A planar `CONTACT` mate declares contact on exactly the large coplanar
   faces where `check_contact` false-fails today; every planar mate on a real part would read
   red.
2. `mate.py`: planar pairs, `CONTACT` and clearance fits, `offset`, `spin`, the declared check;
   the vent rewritten to use it as the acceptance test (it must land where the hand placement
   does, and report 0.20 mm slide).
3. Round pairs (bore and shaft).
4. The app: two-face pick, frame gizmos, **Insert fit**.
5. The section view (its own decision).

## Still the owner's call

- **Two faces, or two faces and their frames?** Recommended: two faces, with the authored
  frame as the rule and `offset`/`spin` to correct it, *plus* the frame gizmo when picking.
  The alternative - snapping to a face's centre, as Fusion's joints do - hides the rule
  instead of showing it, and a centre moves every time the face's shape does.
- **More than one pair?** A pin in a hole *and* a shoulder on a face is two pairs. Recommended:
  one pair per `mated`, a second pair only as a check of where the first put it - bench is
  not a constraint solver, and decision-6 already says an assembly is a scene.
- **Posed geometry versus print geometry.** `mated` moves a body; a part turned over to mate
  would also print turned over unless print orientation (`Orient`) is kept apart from where
  the part sits in the assembly. How posed parts export today has to be checked before step 2.
- **Default `fit` for a planar pair**: `CONTACT`, or required?
