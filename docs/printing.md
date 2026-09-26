# Designing printed parts with bench

A guide for someone writing a bench script for a part that will be printed on an FDM
machine. For each practice it says what to do and why, gives the numbers with their
sources, shows how to do it in bench today, says what bench checks for you, and says how
sure anyone is. It follows the order a designer decides things in: which way up first,
then walls, overhangs, holes, fits and fasteners, and last how to check the result.

## How to read this

**Where the advice comes from.** Three places, and each is marked as it comes up:

- **Slant 3D.** Twenty videos from one channel. Slant 3D is a print farm that sells
  print-on-demand, so its context is mass-production FDM: a 0.4 mm nozzle, auto-ejecting
  machines, an 8.5 x 8.5 in plate
  ([O33g62Kwq9s 02:07](https://www.youtube.com/watch?v=O33g62Kwq9s&t=127s)), and people paid to post-process and assemble. Its rules
  were pulled from the transcripts, checked against them, and merged into 101 rules. Every
  number below links to the second it is said.
- **bench's own code and docs.** These are the authority for how to do something in bench.
  Where this guide names a function, an argument or a constant, it exists as written.
- **The wall vent.** A real four-part printed design built with bench on 2026-09-23: a
  frame screwed to the wall, and attachments that hook onto it. The full project lives
  outside this repository; `examples/wall_vent.py` is a cut-down version of it. What it
  taught is recorded where it applies.

**Evidence labels.** Each Slant rule carries one of two labels:

- *demonstrated*: a part is shown working or failing on camera;
- *claimed*: the presenter says so, and nothing is shown.

No rule is *measured*. No video shows a test with numbers. The count of recordings counts
independent ones only. Two of the twenty videos are compilations that reuse the audio of
others (`vsHpiHhB3RU` and `AAKsl8zW-Ds`), and a rule heard twice in the same recording
counts once.

**Nothing here is measured on bench's printers yet.** bench's own figures are "a starting
point from one reviewer's sources" (`src/bench/library/print.py`). They are not
measurements either. Where bench and Slant disagree, neither side has data, and the
disagreements are collected in [Where bench and the sources disagree](#where-bench-and-the-sources-disagree).
The ones that change geometry bench draws today are the horizontal small hole and the pin
clearance.

**Print-farm economics are not physics.** Some of Slant's rules are about labour and
throughput at volume: minimal bed contact so parts auto-eject, labels on supports for
customers, glue patterns for line workers, no brims because "our machines are not your
machines". They carry over to a one-printer workshop only in part, and they are marked
where they appear.

## Orientation: decide it first

**The rule.** Choose the face each part prints on before drawing anything else. Almost
every other rule depends on it. Which surfaces overhang depends on it. So does whether a
hole's top sags, and which way the layers run through a clip, a pin or a snap arm. A layer
line is the weak direction in FDM: a part pulled across its layers splits along them.

**Why.** An FDM part is strong along a layer and weak between layers. Flex, springs and
snap arms want their bending in the layer plane
([6DkCCOc5O1Y 01:20](https://www.youtube.com/watch?v=6DkCCOc5O1Y&t=80s),
[AAKsl8zW-Ds 09:46](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=586s); claimed, 2
recordings).

**What the sources suggest.**

| Part | Slant's advice | Evidence |
|---|---|---|
| Box-shaped enclosure | Stand it on an edge at about 45 degrees: small bed contact, no internal support, and layer lines that cross screw holes at an angle ([1n_R8shlGcs 04:36](https://www.youtube.com/watch?v=1n_R8shlGcs&t=276s), [8NKVNwVaZU0 02:13](https://www.youtube.com/watch?v=8NKVNwVaZU0&t=133s)) | demonstrated, 2 |
| Slatted vent | Print it so the layers run along each slat. Slats can then go as thin as about **0.5 mm** instead of **1.5 mm** ([bO39lWkaspA 06:48](https://www.youtube.com/watch?v=bO39lWkaspA&t=408s), [08:03](https://www.youtube.com/watch?v=bO39lWkaspA&t=483s), [08:07](https://www.youtube.com/watch?v=bO39lWkaspA&t=487s)) | demonstrated, 1 |
| Ring with clips | Print at a moderate angle. Where clip strength matters, print on edge with the clips **45 degrees** apart rather than opposite ([_y8Yvu1FQIE 01:47](https://www.youtube.com/watch?v=_y8Yvu1FQIE&t=107s), [03:25](https://www.youtube.com/watch?v=_y8Yvu1FQIE&t=205s)) | claimed, 1 |
| Curved surface | Print it on its side rather than as a dome ([ujAwxSx63FE 02:05](https://www.youtube.com/watch?v=ujAwxSx63FE&t=125s)) | claimed, 1 |
| Locating pin | Lie it flat if at all possible ([xog9YlMt9UU 00:19](https://www.youtube.com/watch?v=xog9YlMt9UU&t=19s)) | claimed, 1 |
| Loop-and-pin hinge | The pin in the layer plane, and chunky loops ([BWsUk1xSSn4 02:27](https://www.youtube.com/watch?v=BWsUk1xSSn4&t=147s)) | claimed, 1 |

The 45 degree enclosure is partly a print-farm rule: it exists so the part ejects itself.
The same channel gives up auto-eject on its vent to get the layers along the slats.

**How to do it in bench.** A printed part carries `Printed(material, orient)`, where
`Orient(up=...)` is the build direction in the part's own coordinates and defaults to `+Z`.
Draw the part the way it is easiest to think about, then say which way up it prints:

```python
from bench import *
from bench.library.print import PLA

lid_stock = Printed(PLA, Orient(up=-Z))  # prints on its face, the lip standing up
pin_stock = Printed(PLA, Orient(up=X))   # a pin standing on its end
lid = cuboid(60, 40, 3)
show(part("lid", lid, lid_stock))
```

Every print-aware behaviour reads this `Orient` and nothing else: the teardrop a side hole
gets, the overhang check, and the way a part is laid down when it is exported. A hole
drilled with `top=Top.AUTO` in a body with no `printed=` refuses to guess which way is up.

**The wall vent**, one part at a time. Each part was turned onto the face that made it
printable:

| Part | On the bed | Why |
|---|---|---|
| Frame | its back | the collar and hook lip stand up off it |
| Funnel attachment | its back | the funnel is 45 degrees at its corners, which lean the most |
| Hood | its outlet, standing (`Orient(up=Y)`) | its 45 degree ceiling needs no support |
| Manifold | its socket, upside down (`Orient(up=-Y)`) | a 45 degree hopper leads into the down port, where a flat floor would be a ceiling over nothing |
| Cover | its front | the grille lies flush on the bed; printed back down it would be a ceiling across the whole window |

**A note on pins.** `examples/hinge.py` prints its pin standing on end (`Orient(up=X)`),
which looks like the opposite of Slant's advice to lie pins flat. The two are about different pins.
Slant means a locating pin standing out of a part, which would need support. The hinge pin
is a separate part, and standing up it comes out round.

## Walls

**The rule.** Keep every wall at least two nozzle widths thick, and more where a screw
bears on it.

| What | Figure | Source | Evidence |
|---|---|---|---|
| Any wall or feature | at least **1 mm** (two 0.4 mm lines) | [1n_R8shlGcs 00:13](https://www.youtube.com/watch?v=1n_R8shlGcs&t=13s) | claimed, 1 |
| Walls and flanges at screws and mounts | **2 mm** minimum, up to **5-10 mm** | [8NKVNwVaZU0 01:30](https://www.youtube.com/watch?v=8NKVNwVaZU0&t=90s), [01:33](https://www.youtube.com/watch?v=8NKVNwVaZU0&t=93s) | claimed, 1 |
| Vent slats with the layers along them | down to **0.5 mm** | [bO39lWkaspA 08:07](https://www.youtube.com/watch?v=bO39lWkaspA&t=487s) | demonstrated, 1 |

Slant also advises against carving pockets out of a part to save plastic, as you would
for machining or moulding. The thin walls left behind are weak and unzip along the
layers ([1n_R8shlGcs 02:26](https://www.youtube.com/watch?v=1n_R8shlGcs&t=146s); claimed).
To stiffen a thin compliant part, make it thicker rather than longer
([O33g62Kwq9s 02:53](https://www.youtube.com/watch?v=O33g62Kwq9s&t=173s); claimed). The
channel also contradicts itself here: elsewhere it hollows a mating boss to a thin wall on
purpose, so infill cannot change its size
([XKrDUnZCmQQ 03:47](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=227s); demonstrated).

**In bench.** `Material.min_wall` is 0.86 mm for PLA and PETG and 1.2 mm for ASA.
`check_wall(solid, least)` measures the thinnest wall on the built mesh and reports an
error below `least`. You pass the threshold yourself; it does not default to the
material's. `examples/enclosure_lid.py` writes `check_wall(box, PLA.min_wall)`.

**What it checks, and where it misleads.** `check_wall` casts a ray from the middle of
every triangle into the material, so anything that comes to a point reads as nought
millimetres: a teardrop's apex, or a tab's tip. `examples/depth_stop_collar.py` leaves it
out for that reason, and `examples/fulcrum_hinge.py` for a related one (slivers of wall a
few hundredths of a millimetre wide); both say so. It also compares every
triangle with every other, so it gets slow on big meshes.

**Differs.** For PLA and PETG a wall between 0.86 and 1.0 mm passes bench and fails
Slant's 1 mm. That is about a third of a line width. There is no wall check around a hole.
`shell` (task-70) is planned to check its wall against the printer's minimum.

## Overhangs and chamfers

**The rule.** Nothing may lean further from the build direction than the plastic can hold
up without support. Where an edge would overhang, chamfer it rather than filleting it, or
turn the part.

**Why.** A 45 degree chamfer is one overhang at a steady 45 degrees. A fillet sweeps from
flat to vertical, so its lowest part is a ceiling
([xog9YlMt9UU 04:29](https://www.youtube.com/watch?v=xog9YlMt9UU&t=269s),
[vsHpiHhB3RU 18:28](https://www.youtube.com/watch?v=vsHpiHhB3RU&t=1108s); demonstrated, 2).
Put a chamfer under an overhang instead of relying on generated supports
([1n_R8shlGcs 01:15](https://www.youtube.com/watch?v=1n_R8shlGcs&t=75s),
[_R2E8VwyNz0 01:54](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=114s); claimed, 2). On a
part printed at an angle, round the sharp overhanging edges, which warp, and cut a small
flat for bed contact ([_y8Yvu1FQIE 02:23](https://www.youtube.com/watch?v=_y8Yvu1FQIE&t=143s);
claimed). Slant gives no overhang angle of its own.

Slant separately says to round every *vertical* edge. At a sharp corner the nozzle slows
and bounces, which costs time and accuracy
([1n_R8shlGcs 01:51](https://www.youtube.com/watch?v=1n_R8shlGcs&t=111s),
[XKrDUnZCmQQ 01:16](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=76s); claimed, 2).

**In bench.** `Material.max_overhang` is 45 degrees for PLA and PETG and 40 for ASA.
There is no fillet or chamfer on the edge of a body, and on this kernel there will not be
one. What a maker draws instead:

- Round vertical edges by rounding the sketch before extruding it: `rounded_rect`, or
  `fillet(wire, r, at=...)` and `chamfer(wire, d, at=...)` on the corners of a 2D profile -
  convex or concave corners alike.
- A 45 degree underside by construction: a `loft` from a wide footprint to a narrow one,
  as `examples/pipe_bracket.py` does for its gusset.
- An extrusion with a top, a bottom or both eased round or chamfered:
  `rim(profile, length, lead=..., drop=..., style=...)` from `bench.library.print`, used by
  `examples/eased_bracket.py`; `eased(profile, length, lead=..., drop=...)` is both rims
  chamfered, used by `examples/hinge.py`. Both build the eased end from hulled slices, so
  they are **convex-only**: a profile with a hole or a concave outline is refused with a
  `ValueError` rather than eased into a solid with the notch filled in.

**What bench checks.** `check_overhangs(solid, orient, material)` classifies every triangle
of the built mesh against `orient.up` and reports a warning if any leans past
`max_overhang`. Keep three things in mind:

- It names the single worst face, not all of them. Fix that face and run again.
- It measures an angle, not a span. A flat ceiling reads as 90 degrees whether it is 0.5 mm
  across or 50, so a short bridge that prints fine is still reported. `gridfinity_bin.py`
  does not call it, and `hinge.py` calls it only on the pin; both say why.
- `require()` stops the run on a warning as well as an error, so do not wrap
  `check_overhangs` in `require` unless every face really must pass.

**The wall vent.** `check_overhangs` found a flat ceiling, and the part was redesigned
rather than supported. The finished parts avoid ceilings by construction: the hood's ceiling
is 45 degrees, the manifold's floor is a 45 degree hopper, and the cover prints face-down.
The only warnings left are short bridges of 3-12 mm.

## Bridges

**The rule.** A flat span between two supports prints without support if it is short.
Keep bridges short, and add ribs to break up a long one.

| Figure | Source | Evidence |
|---|---|---|
| **1-2 in** (about 25-51 mm) on most machines | [_R2E8VwyNz0 08:06](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=486s), [bO39lWkaspA 06:00](https://www.youtube.com/watch?v=bO39lWkaspA&t=360s) | claimed, 2 |

The span comes with no material, speed or cooling attached. The same channel says the short
arch at the top of a sideways hole sags enough to matter
([Bd7Yyn61XWQ 01:22](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=82s)). Don't punch a
hole straight through a face that spans an unsupported area, because the strands have
nothing to grip. A one-layer sacrificial skin is acceptable only for small holes that carry
no load ([Bd7Yyn61XWQ 02:19](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=139s),
[03:38](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=218s); demonstrated, 1).

**In bench.** `Material.bridge_max` is 10 mm for PLA, 8 for PETG and 6 for ASA. Its
docstring calls it the longest unsupported span. The only place it is read is when `hole`
chooses a bridged top for a counterbored hole (see Holes). **There is no bridge check.**
`check_overhangs` reports every bridge as a 90 degree face.

**Differs.** Slant's span is 2.5 to 5 times bench's PLA figure. Nothing warns today, so the
two do not clash yet. They will as soon as a bridge check reads `bridge_max` at its current
values. Measure both before choosing (see [Open questions](#open-questions-and-what-we-will-measure)).

## Holes

### Vertical and horizontal

A hole whose axis runs up the build direction prints as a stack of circles and needs
nothing. A hole lying on its side has an arch for a ceiling, and the arch sags. The remedies
are a point at the top (a teardrop), a small flat, or a slightly oval hole in CAD. Slant
stresses them most for precision holes such as screw holes
([Bd7Yyn61XWQ 01:22](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=82s),
[vsHpiHhB3RU 18:28](https://www.youtube.com/watch?v=vsHpiHhB3RU&t=1108s),
[sza8wg5FIxQ 01:11](https://www.youtube.com/watch?v=sza8wg5FIxQ&t=71s); demonstrated, 3
recordings). This is among the best-supported rules in the set.

**In bench.** `hole(..., printed=...)` reads the part's `Orient`. With `top=Top.AUTO`, the
default, `printable_top` chooses the top:

| Lean of the axis from `up` | Drawn diameter | Top it gets |
|---|---|---|
| under 30 degrees (`LEANING`) | any | `ROUND` |
| 30 degrees or more | up to 4 mm (`SHORT_SPAN`) | `ROUND` |
| 30 degrees or more | up to `bridge_max`, counterbored | `BRIDGE` (stepped squares under the counterbore) |
| 30 degrees or more | anything else | `TEARDROP` |

The diameter compared against `SHORT_SPAN` is the drawn one, with compensation already
added. An M3 clearance hole is 3.4 + 0.2 = 3.6 mm in PLA, so it stays round on its side. An
M4 clearance hole is 4.5 + 0.2 = 4.7 mm, so it becomes a teardrop. `AUTO` chooses
`BRIDGE` only for a counterbored hole.

**Differs, and it changes geometry today.** Slant's rule is aimed at exactly the M2-M3 screw
holes that `SHORT_SPAN` keeps round. Until that is measured, ask for the teardrop yourself
where the hole matters:

```python
from bench import *
from bench.library.print import PLA, H2D

pla = Printed(PLA)                       # +Z up: the holes below lie on their side
side = plane(ORIGIN, X, Y)               # a standing sketch plane: u runs +Y, v runs +Z
block = extrude(fill(rect(40, 20), on=side), 20)
face = plane_of(block, "top")            # the face at x = 20, facing +X
block = hole(block, Point(8, 10), on=face, screw=M4, printed=pla,
             label="m4")                 # 4.7 mm drawn: a teardrop by itself
block = hole(block, Point(20, 10), on=face, screw=M3, printed=pla,
             label="m3")                 # 3.6 mm drawn: stays round under SHORT_SPAN
block = hole(block, Point(32, 10), on=face, screw=M3, printed=pla,
             top=Top.TEARDROP, label="m3-point")  # the same hole, pointed on purpose
require(check_fits(block, H2D))
check_overhangs(block, pla.orient, PLA)
show(part("block", block, pla))
```

A teardrop's apex stands `r * sqrt(2)` above the centre, so leave material above it.
`examples/pipe_bracket.py` makes its ear taller for exactly this. `teardrop(d, at, up=...)`
and `bridge_steps(...)` are public too, for a pocket or a lid that needs the profile without
cutting a hole. `d_bore` is a D-shaped profile for a keyed shaft. It is passed as
`profile=`, and it has no printable top of its own, so draw it the way up it prints.

### Compensation

A printed hole comes out undersize. `hole(..., printed=...)` adds the material's
`hole_compensation` to the diameter: 0.20 mm for PLA, 0.25 for PETG, 0.30 for ASA. A
profile is grown by half of that on every edge. Every figure in `bench.fasteners` is the
nominal metal one, so the compensation is always added on top and never baked in.

**The exception is an insert bore.** An insert's bore is quoted as the hole to print, so
`hole(insert=..., printed=...)` draws it exactly - `INSERT_M3`'s 4.2 mm stays 4.2, whether
or not `printed=` is given. `printed=` is still worth passing: it is what `top=Top.AUTO`
reads to choose a top by orientation, so a sideways insert bore gets its teardrop the same
way a screw hole does (see Fasteners).

### Other hole details

- **Lead-in.** Chamfer or round the mouth of a hole that takes a pin, so the pin is guided
  in ([uMA-Wt-z_BU 00:48](https://www.youtube.com/watch?v=uMA-Wt-z_BU&t=48s),
  [vsHpiHhB3RU 18:28](https://www.youtube.com/watch?v=vsHpiHhB3RU&t=1108s); demonstrated,
  2). bench has `LEAD_IN` = 0.4 mm, but only as the `lead_in` field of a `NutTrap` record.
  `hole()` cuts no lead-in. A `lead_in` option on `hole()` is a candidate; task-71's eased
  rims may cover it.
- **Fillet where a hole meets a wall**, rather than leaving a sharp corner
  ([Bd7Yyn61XWQ 00:44](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=44s);
  demonstrated, 1). bench cannot fillet a body's edge.
- **Strong press fit.** Keep the hole at its true diameter and add relief features outside
  it so the wall can spread ([Bd7Yyn61XWQ 04:50](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=290s);
  claimed). For a one-time press fit, ring the hole with small crush ribs. The gaps between
  them also hold glue ([Bd7Yyn61XWQ 05:22](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=322s);
  claimed). See Magnets for what bench has.

## Fits and clearances

### bench's fit table

A `Fit` is an intent: `INTERFERENCE`, `PRESS`, `SNUG`, `SLIDE`, `CLEARANCE`, `LOOSE`.
`clearance(fit, material)` turns it into millimetres **per side**:

| Fit | PLA | PETG | ASA |
|---|---|---|---|
| `INTERFERENCE` | -0.05 | -0.05 | 0.00 |
| `PRESS` | 0.05 | 0.05 | 0.075 |
| `SNUG` | 0.10 | 0.125 | 0.15 |
| `SLIDE` | 0.20 | 0.25 | 0.30 |
| `CLEARANCE` | 0.30 | 0.35 | 0.40 |
| `LOOSE` | 0.50 | 0.55 | 0.60 |

These are starting figures for a 0.4 mm nozzle at 0.2 mm layers. None has been measured on
the machine in the room. Three things about using them:

- **Per side means per side.** A bore that should slide on a 4 mm pin is
  `4 + 2 * clearance(Fit.SLIDE, PLA)` = 4.40 mm.
- **Apply it to one of the two parts.** Taken off both faces, the gap comes out twice as
  wide. `examples/enclosure_lid.py` shrinks only the lid's lip, by `clearance(Fit.SNUG,
  PLA)` a side.
- **`Fit.SLIDE` means two different things.** `clearance(Fit.SLIDE, PLA)` reads the
  material's table: 0.20 per side. `hole(screw=M3, fit=Fit.SLIDE)` reads the screw's ISO
  273 `close` column instead: 3.2 mm, plus compensation. A screw hole's fit and a mating
  fit are different questions with the same names.

### What "slide" comes to in millimetres

For a 4 mm pin in a PLA bore drilled with `hole(diameter=..., printed=...)`:

```python
from bench import *
from bench.library.print import PLA, clearance

pla = Printed(PLA)
pin_d = 4.0
bore_d = pin_d + 2 * clearance(Fit.SLIDE, PLA)   # 4.40: the bore the pin should turn in
plate = cuboid(20, 20, 6)
plate = hole(plate, Point(10, 10), on=plane_of(plate, "top"),
             diameter=bore_d, printed=pla, label="bore")  # drawn 4.60, meant to print at 4.40
print(f"asked {bore_d:.2f}, drawn {bore_d + PLA.hole_compensation:.2f}")
show(part("plate", plate, pla))
```

So in CAD the hole is the pin + 0.60 mm, meant to print as the pin + 0.40. Slant's figure for
a pin hole is "about a quarter of a millimeter" larger than the pin, up to half a millimetre
for high-shrink materials ([uMA-Wt-z_BU 01:03](https://www.youtube.com/watch?v=uMA-Wt-z_BU&t=63s),
[01:05](https://www.youtube.com/watch?v=uMA-Wt-z_BU&t=65s); claimed, 1 recording). Its words
do not say whether that is across the diameter or per side. Slant's figure is for the CAD
model, so compare it with bench's drawn hole, pin + 0.60:

| Reading | Slant's drawn hole | bench's drawn hole (pin + 0.60) |
|---|---|---|
| 0.25 across the diameter | pin + 0.25 | 2.4 times Slant's gap |
| 0.25 per side | pin + 0.50 | 0.10 mm looser than Slant |

Slant's holes also print undersize, so neither side's printed hole is known. Neither reading
is settled. A pin ladder printed on the H2D would settle it.

### Concave arcs: `concave=True`

bench meshes every arc as chords, each sitting up to `CHORD` = 0.05 mm inside the true
circle. Where a gap runs along an internal arc, such as a bore wall, a socket or a groove's
rounded corner, the material bulges into the gap by up to that much. A fit drawn at the bare
figure then measures slightly short. `clearance(fit, material, concave=True)` adds `CHORD`
to the figure, so the drawn geometry keeps its fit once it is meshed.

**The wall vent.** The attachment's groove round the frame's collar has rounded corners. Drawn
at the plain `SLIDE` figure, `check_fit` measured it at 0.199 against 0.200 asked, a
thousandth short, because the corners' chords lie inside their arcs. Drawn with `concave=True` (0.25 per side), it measured
clear by 0.248 against 0.200. `examples/wall_vent.py` draws it the second way.

### Geometry that carries the fit

Slant's broader stance is that geometry, not slicer tuning, should carry the fit, so the
part works on any machine ([uMA-Wt-z_BU 06:31](https://www.youtube.com/watch?v=uMA-Wt-z_BU&t=391s),
[BWsUk1xSSn4 07:44](https://www.youtube.com/watch?v=BWsUk1xSSn4&t=464s),
[MCcFMDv_4eo 01:32](https://www.youtube.com/watch?v=MCcFMDv_4eo&t=92s); claimed, 3). bench
compensates per material in geometry instead. The two approaches can be combined, and
several of Slant's techniques are well supported:

- **Wedge fits.** Taper one of the two mating faces, so the fit starts loose and tightens
  as it seats ([XKrDUnZCmQQ 02:11](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=131s),
  [uMA-Wt-z_BU 03:57](https://www.youtube.com/watch?v=uMA-Wt-z_BU&t=237s),
  [Bd7Yyn61XWQ 04:16](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=256s),
  [vsHpiHhB3RU 21:26](https://www.youtube.com/watch?v=vsHpiHhB3RU&t=1286s); demonstrated,
  4). In bench a taper is a `loft`. `examples/systainer_tote.py` builds tapered plugs and
  their sockets that way.
- **Grip fins.** Flexible fingers round a hole, undercut so they flex, grip with a steady
  force whatever the machine or material
  ([Bd7Yyn61XWQ 06:14](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=374s),
  [XKrDUnZCmQQ 10:26](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=626s),
  [RTQjvYENR7w 05:14](https://www.youtube.com/watch?v=RTQjvYENR7w&t=314s); demonstrated,
  3). The only number is one example: fins with an **11 mm** inside diameter for a 12 mm rod
  ([Bd7Yyn61XWQ 07:14](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=434s)). bench has no
  grip-fin feature; it is a candidate for the planned `flexures` library.
- **Compliance in general.** Carry a tight tolerance with edge cutouts or thin walls that
  touch at a few points and can flex
  ([1n_R8shlGcs 03:36](https://www.youtube.com/watch?v=1n_R8shlGcs&t=216s),
  [XKrDUnZCmQQ 04:36](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=276s); demonstrated,
  2). Splits cut into rigid corners are another form. Keep the splay to about **0.5 mm**
  ([XKrDUnZCmQQ 09:32](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=572s); claimed).
- **Lids.** Relieve a box lid's corners so only the flat sides touch
  ([XKrDUnZCmQQ 08:15](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=495s); demonstrated,
  1).

## Fasteners

### Screws

`hole(screw=M3, fit=..., printed=...)` sizes a screw hole from the ISO table. Pass
`countersink=True` for a 90 degree cone (`COUNTERSINK`), which is also a printable 45
degree overhang, or `counterbore=True` for a socket head. Sizes run `M2`, `M2_5`, `M3`,
`M4`, `M5`, `M6`, `M8`.

**Imperial (task-69).** The vent drew its #6 drywall screws as M4 for want of a table
entry; `fasteners.py` now carries `WOOD_6`, `WOOD_8`, `WOOD_10` (flat head wood screws),
`DRYWALL_6`, `DRYWALL_8`, `DRYWALL_10` (bugle head drywall screws, the same thread and
clearance holes as the wood ones - a bugle head changes the head, not what the screw drives
into) and `MACHINE_8_32`, `MACHINE_10_24`, `MACHINE_1_4_20`. Every figure is cited in the
module: ASME B18.6.1's own diameter formula and flat head for the wood screws,
ANSI/ASME B18.2.8 for the clearance holes (the inch counterpart of the metric table's ISO
273), a softwood/hardwood pilot chart for `tap`/`self_tap` (shop practice, not a
dimensional standard - ASME B18.6.1 does not set it either), and ASME B18.6.3 plus ASME
B18.3 for the machine screws' thread, head and countersink. `hole(screw=DRYWALL_6, ...)`
works exactly like a metric one: `DRYWALL_6.diameter` is 3.51 mm, between M3 and M4 and
nothing like either.

American flat and bugle heads sink at 82 degrees, not the metric table's ISO 90 - every
imperial screw here carries that as `countersink_angle`, and a drywall screw's bugle head
carries its own, narrower estimate (`BUGLE`, about 61.5 degrees - neither ASME table gives
a bugle head an angle at all, so this is flagged as an estimate rather than a citation).
`hole(..., countersink=True)` cuts the cone at the screw's own `countersink_angle` - 90 for
a metric screw, 82 for an inch flat head, `BUGLE` for a drywall screw - and `angle=` is
there only to override it. The narrower a cone, the deeper it sinks to the same diameter at
the surface: a bugle countersink goes about half as deep again as a flat head's.

Socket head, button head, counterbore and nut figures are `0.0` on every wood and drywall
screw - nobody makes one with a hex socket or runs a nut on one - and on the machine screws
the counterbore and nut columns are `0.0` too: this reviewer reached three disagreeing
inch counterbore tables and an inch hex nut table split awkwardly across two standards, and
left both at nothing rather than guessing between them. A `0.0` column fails loudly (a
cutter with no size) rather than lying with an invented figure.

**Self-tapping.** A plain hole slightly under the screw works for small screws and
low-stakes joins, with at least **1 mm** of wall round it. For a large screw such as M10 it
splits the boss and survives one use
([sza8wg5FIxQ 01:00](https://www.youtube.com/watch?v=sza8wg5FIxQ&t=60s),
[WMbmDfGEygk 01:19](https://www.youtube.com/watch?v=WMbmDfGEygk&t=79s); claimed, 2).
Relief ribs inside the hole give the screw something to cut into instead of pushing the
whole wall outward ([WMbmDfGEygk 01:51](https://www.youtube.com/watch?v=WMbmDfGEygk&t=111s);
claimed). In bench, `hole(screw=M3, fit=Fit.PRESS)` reads the screw's `self_tap` column
(2.6 mm for M3). bench does not check the wall round it.

### Heat-set inserts

Leave the hole sized for the insert, with about **1-2 mm** of solid material round it
([sza8wg5FIxQ 01:51](https://www.youtube.com/watch?v=sza8wg5FIxQ&t=111s); claimed). bench's
`Insert` docstring asks for 1.6 to 2 mm, stricter at the low end. Neither is checked.
`INSERT_M3`, `INSERT_M4` and `INSERT_M5` carry the insert's `od`, `length` and the `bore`
to print. Draw the bore exactly, as `examples/enclosure_lid.py` does:

```python
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
boss_d = INSERT_M3.od + 2 * 2.0          # 2 mm of plastic round the insert
boss = cylinder(boss_d / 2, 10.0, label="boss")
boss = hole(boss, ORIGIN, on=plane_of(boss, "boss/top"), insert=INSERT_M3,
            depth=INSERT_M3.length + 1.0, printed=pla,
            label="insert")              # drawn at 4.2 mm: printed= never inflates an insert bore
show(part("boss", boss, pla))
```

`printed=` is the plain call, upright or sideways: it never adds compensation to an insert
bore, so the hole stays 4.2 mm either way, and it is still what `top=Top.AUTO` reads to
choose the top - round for the upright boss above, a teardrop without being asked if the
same boss were drilled from the side.

### Nuts

Don't design parts that need a pause mid-print to drop hardware in; design so hardware goes
in afterwards ([WMbmDfGEygk 00:00](https://www.youtube.com/watch?v=WMbmDfGEygk&t=0s);
claimed). Another Slant video does the opposite for maximum pull-out strength, pausing to
print over a nut ([sza8wg5FIxQ 02:33](https://www.youtube.com/watch?v=sza8wg5FIxQ&t=153s);
demonstrated). Without a pause, there are three options:

- **Rear channel.** A hex channel from the back up to where the nut sits
  ([WMbmDfGEygk 02:52](https://www.youtube.com/watch?v=WMbmDfGEygk&t=172s); claimed).
- **Side slot.** Works, but puts a stress concentration in the layer plane
  ([WMbmDfGEygk 04:39](https://www.youtube.com/watch?v=WMbmDfGEygk&t=279s); claimed).
- **Drop-in.** A top slot slightly narrower than the nut above a wider channel. The nut
  settles about **2 mm** below the opening and the screw pulls it up
  ([WMbmDfGEygk 06:27](https://www.youtube.com/watch?v=WMbmDfGEygk&t=387s); claimed).

**In bench, the numbers only.** `nut_trap(screw)` returns a `NutTrap` record: the pocket's
`across_flats` (the screw's `nut_trap_across_flats`, a tenth or two over the nut), its
`depth`, and a `lead_in` of `LEAD_IN` = 0.4 mm. No function cuts the pocket. Draw the hexagon
yourself with `polygon` and cut it, and cut the lead-in too if you want one.

**task-75.** This is not bench already agreeing with Slant's hardware options above - it is
only the numbers agreeing. No public operation cuts a nut trap or a set of crush ribs today;
the rib geometry that does exist is private to `gridfinity3d._ribs`, one library's own
shape, not a verb the vocabulary offers. Whether cutting a nut trap and a ring of crush ribs
become public operations is left to decision-11's own order: `flexures` and `enclosures`
will want both, and each gets its own decision when its turn comes, the way `shell` and the
others in the decision's table already do.

### Magnets

`MAGNET_6X2` is gridfinity-rebuilt's pocket for a 6 x 2 mm magnet: a 6.5 mm hole with eight
5.9 mm crush ribs, which crush as the magnet goes in. The rib geometry is built inside
`bench.library.gridfinity3d` and is not public (see task-75, above). Anywhere else, the
`Magnet` record gives the numbers and you draw the ribs yourself (`pattern` with a `Turn`
places copies round a circle). The vent's magnet pockets had no ribs, so its magnets are
glued.

## Joining parts

Slant's joints, most from one recording each and nearly all claimed:

| Joint | What Slant says | Source |
|---|---|---|
| Pins | Make them fat. Fillet or chamfer the base, where they break along the layers. Round the tip, and keep them no longer than needed. Use no more locators than the degrees of freedom need: two pins locate a lid | [uMA-Wt-z_BU 01:18](https://www.youtube.com/watch?v=uMA-Wt-z_BU&t=78s), [xog9YlMt9UU 01:17](https://www.youtube.com/watch?v=xog9YlMt9UU&t=77s), [01:40](https://www.youtube.com/watch?v=xog9YlMt9UU&t=100s) |
| Cross-section pin | A plus-shaped section for more layer contact in the push direction | [uMA-Wt-z_BU 03:15](https://www.youtube.com/watch?v=uMA-Wt-z_BU&t=195s) |
| Keyhole pin | A horizontal pin chamfered top and bottom, so it prints any way up (demonstrated) | [vsHpiHhB3RU 20:13](https://www.youtube.com/watch?v=vsHpiHhB3RU&t=1213s) |
| Diamond peg | A square peg turned 45 degrees: no overhang, strong lying down | [djm5tCFn9S0 00:41](https://www.youtube.com/watch?v=djm5tCFn9S0&t=41s) |
| Fin and slot | Replaces pin and hole: more contact, easier to find. Chamfer, don't fillet, a vertical fin's faces | [xog9YlMt9UU 03:09](https://www.youtube.com/watch?v=xog9YlMt9UU&t=189s) |
| Tongue and slot | Chamfer the tongue so it wedges. It still has tolerance problems and no pull-together | [RTQjvYENR7w 00:40](https://www.youtube.com/watch?v=RTQjvYENR7w&t=40s) |
| Round tongue and eye | Better than a T-slot: one concentric dimension, and a round first layer that warps less | [RTQjvYENR7w 03:46](https://www.youtube.com/watch?v=RTQjvYENR7w&t=226s) |
| Lock-in tab | Two flexing bumps into two recesses, with angled flanges that need no support (demonstrated) | [RTQjvYENR7w 06:56](https://www.youtube.com/watch?v=RTQjvYENR7w&t=416s) |
| Slab and slot | For thin parts. Taper the slab's ends so it self-aligns. Avoid broad flat faces, which spring back and leave a gap | [djm5tCFn9S0 01:16](https://www.youtube.com/watch?v=djm5tCFn9S0&t=76s), [01:40](https://www.youtube.com/watch?v=djm5tCFn9S0&t=100s) |
| S-bracket | A separate S-shaped clip through slots in both parts; its size tunes the compression | [djm5tCFn9S0 02:14](https://www.youtube.com/watch?v=djm5tCFn9S0&t=134s) |
| Glue joints | Undercut relief so glue keys in; a moulded pattern showing where glue goes; an internal channel to inject glue after assembly | [vsHpiHhB3RU 14:33](https://www.youtube.com/watch?v=vsHpiHhB3RU&t=873s), [15:23](https://www.youtube.com/watch?v=vsHpiHhB3RU&t=923s), [16:18](https://www.youtube.com/watch?v=vsHpiHhB3RU&t=978s) |

**In bench.** None of these is a library feature. All of them can be drawn with the
vocabulary: a diamond peg is a rotated `rect` extruded, a chamfered tongue is a `polygon` or
a `loft`, and a fin is a thin `cuboid`. What bench adds is placing and measuring the pair.
`mated(fixed, at, moving, onto, fit=...)` puts one part's face on another's and measures the
pair at the fit it was asked for, in the same call. A pin in its bore goes on the bore's
axis. `check_fit(a, b, fit, material)` measures a second pair beside the mate, such as a
groove round a collar.

The vent's hood is glued to the adapter's front, declared with `check_contact` (they must
touch and not overlap). The manifold's socket is glued over the hood's outlet at `SLIDE`,
with the gap left for the glue.

## Flexures: snaps, living hinges, springs

**The rule.** Anything that flexes must bend in the layer plane, and must not strain the
plastic past what it takes.

**From Slant.**

- **Snap tabs.** Turn a snap tab sideways so it flexes along its layers. Never print a
  spring at an angle to its load
  ([6DkCCOc5O1Y 01:20](https://www.youtube.com/watch?v=6DkCCOc5O1Y&t=80s),
  [AAKsl8zW-Ds 09:46](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=586s); claimed, 2). A
  sideways tab can be held up by a designed sprue about **1 mm** across, flicked off after
  printing ([6DkCCOc5O1Y 02:25](https://www.youtube.com/watch?v=6DkCCOc5O1Y&t=145s);
  claimed).
- **Clips.** Chamfering a clip's outer edges strengthens it but stiffens it
  ([_y8Yvu1FQIE 01:16](https://www.youtube.com/watch?v=_y8Yvu1FQIE&t=76s); claimed).
- **Living hinges.** A thin flat living hinge fatigues and cannot bend far, and it wants a
  tough material: TPU or PP, and PETG rather than PLA
  ([AAKsl8zW-Ds 01:01](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=61s),
  [BWsUk1xSSn4 00:36](https://www.youtube.com/watch?v=BWsUk1xSSn4&t=36s); claimed, 2).
  Alternatives, each demonstrated once: a circular loop hinge that spreads the bend
  ([AAKsl8zW-Ds 01:25](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=85s)), the loop with
  teeth cut in for more range
  ([01:52](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=112s)), and a slotted kerf hinge
  that twists rather than creases
  ([03:22](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=202s),
  [BWsUk1xSSn4 01:44](https://www.youtube.com/watch?v=BWsUk1xSSn4&t=104s)).
- **Springs.** Never a helical coil spring, which has no path in a printable plane
  ([AAKsl8zW-Ds 05:53](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=353s); claimed).
  Instead: a flat serpentine with rounded corners, thinned to about **1 mm** to soften it
  ([07:30](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=450s); demonstrated); leaf
  springs; or a flat spiral for stored energy
  ([10:36](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=636s); claimed).

**In bench.** There is no flexure feature, and `Fit` deliberately has no `SNAP` member.
What latches a snap is arm length, thickness and deflection, not a gap. Nothing checks
which way a snap arm bends relative to `Orient.up`. The planned `flexures` library (in
decision-11) is to cover snap latches, annular snaps and living hinges, with a strain limit
added to `Material`.

**The wall vent's latch, sized by hand.** Every attachment has two snap latches: a beam cut
free on three sides with a 30 degree ramped bump on its end. The beam lies flat on the bed,
so it bends along its layers. It was sized with the textbook cantilever formulas:

- peak strain at the root: `1.5 * T * d / L**2`, for thickness `T`, deflection `d` and
  length `L`;
- force at the tip: `3 * E * I * d / L**3`, with `I = b * T**3 / 12`.

The strain is checked against about 2% for PLA, and the script refuses a latch that would
exceed it. With 3 mm x 30 mm latches flexing about 3.4 mm, that is about 1.7% strain, and
about 7 kgf to lift the attachment off past the magnets. Both constants are the project's
own and unmeasured: 2% for PLA's strain, and E = 2300 MPa, the low end for printed PLA.
The latch's fit test moves the attachment with its bumps left off, as if already flexed flat,
so the clearance walk does not test the latch. Only the arithmetic does.

## Print-in-place

**The rule.** Leave a gap between parts printed already assembled: large enough that the
slicer does not close it, small enough that the part keeps its shape.

| Figure | Source | Evidence |
|---|---|---|
| Gap under a flexing or print-in-place feature: at least about **0.3 mm** | [XKrDUnZCmQQ 05:37](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=337s) | demonstrated, 1 |
| At most about **0.5 mm**, beyond which the feature starts to deform | [XKrDUnZCmQQ 06:09](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=369s) | demonstrated, 1 |

On hinges printed in place, all demonstrated once:

- An axle hinge printed vertically turns smoothly but is weak in torsion. Chamfer the axle's
  inner edges so the layers don't fuse. Printed horizontally it is stronger but rougher
  ([AAKsl8zW-Ds 04:16](https://www.youtube.com/watch?v=AAKsl8zW-Ds&t=256s)).
- A single-cone hinge turns freely with no side play, but is weak in twisting, so make it big
  ([BWsUk1xSSn4 03:41](https://www.youtube.com/watch?v=BWsUk1xSSn4&t=221s)).
- A double-cone hinge has an overhang where one link settles onto the other. Remove it by
  blending the cones through a chamfered span, or by printing the hinge on its side
  ([04:50](https://www.youtube.com/watch?v=BWsUk1xSSn4&t=290s),
  [05:18](https://www.youtube.com/watch?v=BWsUk1xSSn4&t=318s),
  [06:13](https://www.youtube.com/watch?v=BWsUk1xSSn4&t=373s)).

**In bench.** There is no print-in-place gap. The nearest figure is PLA's `SLIDE`, 0.20 per
side, and a print-in-place joint sized from it would sit under Slant's 0.3 floor. Use a gap
of your own until `flexures` has one. `check_clearance(a, b, least)` checks two bodies stay
`least` apart, and `check_clearance_through` checks the same across a motion (see Checking).

## Designed-in supports

Slant prefers designing a support into the model over slicer supports, so the support is
the same on every machine. All of these rest on one channel, and most on one recording:

| Support | What it is | Figures |
|---|---|---|
| Support fin | For a part printed at an angle: a 45 degree or triangular fin set off the part, joined by thin prongs that snap off (demonstrated, 2) | fin **0.5-1 mm** from the part ([8NKVNwVaZU0 03:11](https://www.youtube.com/watch?v=8NKVNwVaZU0&t=191s)); prongs **0.5 mm** thick ([_R2E8VwyNz0 06:53](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=413s)) and **0.5-1 mm** wide ([06:57](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=417s)) |
| Designed body | A body offset from the part's contour, test-printed before trusting it | **2-3 mm** spacing ([_R2E8VwyNz0 04:26](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=266s)) |
| Bridge block | A block under a bridge, with a hole so it can be crushed out | **0.2 mm** clearance above, **0.2-0.3** below ([_R2E8VwyNz0 08:22](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=502s), [08:26](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=506s)); read from garbled captions |
| Thumbtack | A small spike with a broad base under an isolated overhang tip (demonstrated, 1) | [_R2E8VwyNz0 02:34](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=154s) |

Slant also braces a tall support with small sprues ([_R2E8VwyNz0 05:04](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=304s)),
gives a thin fin a wide base so it does not peel ([8NKVNwVaZU0 03:55](https://www.youtube.com/watch?v=8NKVNwVaZU0&t=235s)),
and embosses "support" on it so whoever cleans the part knows to remove it
([_R2E8VwyNz0 08:38](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=518s)). The last is a
print-farm habit.

**In bench.** Nothing, and no decision plans a supports library. Before designing a support,
turn the part or chamfer the overhang, as the vent did for every part.

## Bed contact

**Bottom edge.** Slant says to always chamfer the edge that sits on the bed, to take off the
elephant's foot: the first layers spread under the weight above them
([XKrDUnZCmQQ 01:58](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=118s),
[_y8Yvu1FQIE 01:32](https://www.youtube.com/watch?v=_y8Yvu1FQIE&t=92s); claimed, 2). It calls
the chamfer mostly cosmetic. The second source may say fillet, but its caption is garbled.

In bench, `foot_chamfer(solid, d)` cuts a 45 degree chamfer `d` tall off the face an
extrusion stands on. `Material.foot` is the first-layer spread: 0.15 mm for PLA, 0.20 for
PETG and 0.25 for ASA. `foot_chamfer` only accepts a plain extrusion, so apply it first,
before any union or cut:

```python
from bench import *
from bench.library.print import PLA

pla = Printed(PLA)
base = foot_chamfer(cuboid(60, 30, 5), PLA.foot * 3)   # first, while it is one extrusion
base = hole(base, Point(15, 15), on=plane_of(base, "top"), screw=M4,
            printed=pla, label="screw")
show(part("base", base, pla))
```

The chamfer's size is your choice. `examples/pipe_bracket.py` uses three times `foot`, as
above, and is the only example that calls `foot_chamfer` at all. On a concave footprint the
taper is a hull, which leaves re-entrant corners under-cut. **Differs:** Slant treats the
chamfer as a default, bench as an opt-in tool.

**Keep the first layer simple.** No sharp corners and no text, as near round as possible. If
a mechanism's first layer is complicated, print it on a solid plate about **1 mm** thick that
acts as a built-in raft ([1n_R8shlGcs 01:20](https://www.youtube.com/watch?v=1n_R8shlGcs&t=80s),
[O33g62Kwq9s 04:47](https://www.youtube.com/watch?v=O33g62Kwq9s&t=287s); claimed, 2).

**Mouse ears.** Instead of a brim, model small discs about **0.2 mm** thick at sharp corners.
Better still, put each disc on a narrow neck and snip it off like a sprue
([MCcFMDv_4eo 02:20](https://www.youtube.com/watch?v=MCcFMDv_4eo&t=140s),
[02:51](https://www.youtube.com/watch?v=MCcFMDv_4eo&t=171s); demonstrated, 1). 0.2 mm is also
bench's layer height (`Material.layer`). bench has no mouse-ear feature, but a disc is a
`cylinder` one layer tall, unioned at the corner.

## Threads

Directly modelled plastic threads are reliable only from about **1/8 in** (3.2 mm) up, and
M3 and smaller do not work on a 0.4 mm nozzle. Keep every printed thread feature at least
**0.2-0.4 mm** ([sza8wg5FIxQ 03:59](https://www.youtube.com/watch?v=sza8wg5FIxQ&t=239s),
[04:08](https://www.youtube.com/watch?v=sza8wg5FIxQ&t=248s); demonstrated, 1). For a
horizontal thread, cut away the top and bottom of the profile and keep only the side flanks
([sza8wg5FIxQ 05:33](https://www.youtube.com/watch?v=sza8wg5FIxQ&t=333s); demonstrated, 1).

**In bench.** `thread(Thread.EXTERNAL | Thread.INTERNAL, diameter, pitch, length)` is a
twisted extrusion of an offset circle, used by `examples/jar_lid.py`. The external thread is
drawn nominal. The internal one is opened by the fit table's clearance, stood square across
its steepest flank, and grown by the material's `hole_compensation` like any printed hole -
added once, by `thread` itself. So the model's gap is the clearance plus half the
compensation across the flank (an M12 x 2 in PLA at a slide measures 0.28 mm for 0.20
asked), and on a fine thread the model's nut no longer engages its bolt - it would slide
straight off along the axis - because an M8 x 1.25's opening is deeper than its 0.33 mm
thread. The print, shrinking the cavity by that compensation, is what is meant to close it,
and the run says so: an internal thread opened as far as it is deep is a `thread` warning,
"drawn clear of its bolt". At the default depth that is every pitch under about 1.54 mm in
PLA at `Fit.SLIDE` (2.03 at `CLEARANCE`; PETG 1.88 and 2.37; ASA 2.22 and 2.70) - a coarser
pitch or a deeper thread engages in the model.
A thread under 3.2 mm across or 0.4 mm deep is built and warned about, never refused: the
warning is a `thread` finding in the Problems panel and `tools.build`'s summary, at the
script's line, because both limits are Slant 3D's and unmeasured here.

## Big parts and bed fit

A part that can only lie flat is limited by the plate's diagonal. On Slant's 8.5 in plate
that is "only about 10 in" ([O33g62Kwq9s 02:07](https://www.youtube.com/watch?v=O33g62Kwq9s&t=127s),
[02:32](https://www.youtube.com/watch?v=O33g62Kwq9s&t=152s); claimed, 1). The arithmetic is
loose: an 8.5 in square has a 12 in diagonal, so 10 in presumably allows for the part's
width.

**In bench.** `check_fits(shape_or_part, volume, orient=None)` compares the part's
axis-aligned box against a `Volume` - lying down the way it prints, when something says how.
`H2D` is 350 x 320 x 325 mm, and `BEDS` names it and the 256 mm Bambu machines. It needs no
kernel, so it runs everywhere. One limit remains:

- It does not try the part turned on the bed, so a long part that would fit diagonally is
  rejected. That errs on the safe side.

It used to measure the part where it is drawn, not the way it prints: the vent's hood, which
prints standing on its outlet, read "y 322.4 mm against 320" although it stands 322 mm tall
in a 325 mm build height. task-68 fixed it - `check_fits` reads a printed `Part`'s own
`Orient` when it is handed the `Part` rather than its bare shape, and `orient=` states one
for a bare solid instead:

```python
from bench import *
from bench.library.print import PLA, H2D

standing = Printed(PLA, Orient(up=Y))    # prints standing on its -Y face
hood = cuboid(300, 322, 80)
require(check_fits(part("hood", hood, standing), H2D))
show(part("hood", hood, standing))
```

ASA shrinks 0.7 per cent (`Material.shrink`), 2.4 mm across a 350 mm bed. bench records
shrink but does not apply it.

## Checking a design in bench

### The checks

Every check records what it finds and returns it. `require(...)` makes a finding stop the
run. A check that needs the modeller and has none answers **not checked**, never a pass. The
command-line `tools.build` loads no modeller, so there only `check_fits` answers.

| Check | Question | Needs the modeller |
|---|---|---|
| `check_fits(shape_or_part, volume, orient=None)` | does the box, as it prints, fit the build volume | no |
| `check_wall(solid, least)` | is the thinnest wall at least `least` | yes |
| `check_overhangs(solid, orient, material)` | does any face lean past `max_overhang` (warning, worst face) | yes |
| `check_clearance(a, b, least)` | do two bodies stay `least` apart | yes |
| `check_clearance_within(assembly, least, exclude=...)` | the same for every pair in an assembly | yes |
| `check_contact(a, b)` | two bodies meant to touch: do they touch without overlapping | yes |
| `check_fit(a, b, fit, material)` | how far apart a pair really is, against the fit's gap | yes |
| `mated(fixed, at, moving, onto, fit=...)` | places a part by a face and measures that pair | yes |
| `check_clearance_through(at, least, samples=...)` | do all pairs stay apart across a motion | yes |

### Fit tests along the path a part goes on

A fit that is clear where the part ends up can still collide on the way there. Test the
motion: write a function that poses the assembly at a parameter, and ask
`check_clearance_through` to walk it.

```python
from bench import *
from bench.library.print import PLA, clearance

pla = Printed(PLA)
gap = clearance(Fit.SLIDE, PLA)
sleeve = cut(cuboid(30, 30, 40),
             cuboid(20 + 2 * gap, 20 + 2 * gap, 42, at=Point(5 - gap, 5 - gap, -1)),
             label="bore")
bar = cuboid(20, 20, 60, at=Point(5, 5, 0), label="bar")


def at(s: float) -> Assembly:
    """The bar pushed up into the sleeve, from clear below it (0) to home (1)."""
    return assembly("slide", (
        Placed(part("sleeve", sleeve, pla), XY),
        Placed(part("bar", move(bar, Z * (65.0 * (s - 1))), pla), XY),
    ), posed=True)


print(check_clearance_through(at, gap * 0.99, samples=21))
show(at(1.0))
```

It samples: the answer is a `Sampled` whose sentence gives the number of poses and the
spacing, because "clear at 21 poses" is not "clear throughout". It says nothing about force,
friction or binding. Pairs meant to seat against each other go in `contacts=`, which checks
them with `check_contact` at every pose instead.

**The wall vent** walks each attachment along the path a person hangs it by: held off and
raised, pushed onto the collar, dropped onto the hook. It also slides the manifold up onto
the hood. The walk found a real collision: a manifold sleeve that reached back to the wall
met the frame's flange on the way on (the walk reported 0.17 mm at 0.375 of the path), so
the sleeve now stops short of the flange.

**A test proves something only if it can be shown to fail.** A clean result from a check
that could never have failed says nothing. Before trusting one, break the design on purpose:
narrow the gap, lengthen the part, or move the pose past where it collides. Then check that
the check reports it. The vent's latches are an example of where a test is blind. Its fit
tests move the attachment with the latch bumps left off, so no clearance walk can fail on a
latch, and only the strain arithmetic tests it.

### Looking at it in the app

The viewer draws what the checks measured, and three tools help you read a fit hidden inside
a part:

- **section** clips the view at a plane on X, Y or Z, with a slider for where, and shows cut
  material in flat red. It stays on while knobs change, so dragging a pose knob animates the
  section.
- **colour faces** paints every named face a different colour, so you can see which face
  is which, and which ref to pass to `plane_of` or `mated`.
- **The refs tree** has an eye on every part and face row to hide it, **only** on a part to
  isolate it, and **show all**. A finding on a hidden part is still listed.

## Where bench and the sources disagree

In each case neither side has measured anything. The rows are ordered by effect.

| Rule | Slant 3D | bench today | What it means |
|---|---|---|---|
| Small horizontal holes | Point or flatten the top, especially on screw holes ([Bd7Yyn61XWQ 01:22](https://www.youtube.com/watch?v=Bd7Yyn61XWQ&t=82s)) | `SHORT_SPAN` = 4 mm keeps M2-M3 screw holes round on their side | Changes geometry today. Ask for `top=Top.TEARDROP` where it matters |
| Pin clearance | about 0.25 mm, up to 0.5 ([uMA-Wt-z_BU 01:03](https://www.youtube.com/watch?v=uMA-Wt-z_BU&t=63s)) | `SLIDE` is 0.20 per side: pin + 0.60 drawn, meant to print at pin + 0.40 | Drawn against drawn: 2.4 times Slant's gap if Slant meant diametral, 0.10 mm looser if per side |
| Bridge span | 1-2 in ([_R2E8VwyNz0 08:06](https://www.youtube.com/watch?v=_R2E8VwyNz0&t=486s)) | `bridge_max` 10/8/6 mm, read only for counterbore tops; no bridge check | No clash yet; a bridge check at these values would flag spans Slant calls routine |
| Minimum wall | 1 mm ([1n_R8shlGcs 00:13](https://www.youtube.com/watch?v=1n_R8shlGcs&t=13s)) | `min_wall` 0.86 PLA and PETG, 1.2 ASA; `check_wall` takes its threshold from you | 0.86-1.0 mm passes bench, fails Slant |
| Insert wall | 1-2 mm ([sza8wg5FIxQ 01:51](https://www.youtube.com/watch?v=sza8wg5FIxQ&t=111s)) | 1.6-2 mm in the `Insert` docstring; not checked | bench asks more at the low end |
| Print-in-place gap | 0.3-0.5 mm ([XKrDUnZCmQQ 05:37](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=337s)) | none; `SLIDE` is 0.20 | A joint sized from `SLIDE` would sit under Slant's floor |
| Bottom chamfer | always ([XKrDUnZCmQQ 01:58](https://www.youtube.com/watch?v=XKrDUnZCmQQ&t=118s)) | `foot_chamfer` is opt-in | Default against tool |
| Plate diagonal | a part may lie across the plate ([O33g62Kwq9s 02:32](https://www.youtube.com/watch?v=O33g62Kwq9s&t=152s)) | `check_fits` measures the box as drawn, unturned | bench is conservative for long thin parts |

## Open questions and what we will measure

1. **Horizontal screw holes.** Print M2-M4 clearance holes lying on their side, round against
   teardrop, on the H2D, and gauge them. Then decide whether `SHORT_SPAN` should apply to
   screw holes at all.
2. **Pin clearance.** Decide whether Slant's 0.25 is diametral or per side, then print a pin
   ladder and see which `Fit` row it matches.
3. **Bridges.** Print a bridge-length test per material. Decide whether `bridge_max` is a
   general span (so it needs a check) or only the widest counterbore ceiling (so it needs a
   new name).
4. **Minimum wall.** Measure it, then decide whether 0.86 becomes 1.0 and whether
   `check_wall` should default to `min_wall`.
5. **Defaults or checks.** Should bench add a foot chamfer and a hole lead-in by default, or
   warn when they are missing?
6. **Print-in-place and flexures.** A gap for print-in-place, and a strain limit per
   material, both for the planned `flexures` library. The vent's 2% for PLA is a starting
   figure only.
7. **Threads.** Print M3-M8 modelled threads before task-72 decides where to warn.
8. **Supports.** Does bench want designed supports at all? No decision covers them.
9. **Unwatched claims.** One rule, a locating pin made into a cone "within 30 degrees"
   ([xog9YlMt9UU 01:33](https://www.youtube.com/watch?v=xog9YlMt9UU&t=93s)), is left out of
   this guide: nothing says what the 30 degrees is measured from. Someone needs to watch the
   clip.

When any of these is measured, the number changes in one place (`src/bench/library/print.py`
or `src/bench/fasteners.py`), and this guide should change with it.
