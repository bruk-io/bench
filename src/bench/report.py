"""Report: a survey written out for a person, or for a model drafting a first attempt.

:func:`bench.survey.survey` answers with a record, and a record is not what anyone reads.
This module takes that record and nothing else - it never sees the mesh, and imports nothing
that could - and returns text. The wording is the whole job: a measurement put in bench's own
words, "an outline this big at this height", "a bore of this diameter on this spacing",
reads as a script waiting to be typed, and the same measurement as bare coordinates reads as a
point cloud.

Three rules hold every line.

*It offers, it does not conclude.* Every line that names a verb is marked ``candidate`` and
says what measured fact it fits. Which verb a maker reaches for is theirs to decide; the report
says which ones fit the numbers.

*It says nothing that was not measured.* A 4.000 mm bore is a 4.000 mm bore. Which screw, which
fit or which nominal asked for it is not in the mesh, so it is not in the report, and the last
section says so in as many words. A survey's own limits come through undiluted: the single
thinnest reading is reported beside the area that measured it, so a sliver of the
tessellation is not mistaken for a wall, and the closing notes say what the survey cannot see.

*The same survey renders the same report.* Every list is sorted here on the numbers in it, so
the order records arrived in does not show, and every number is printed to a fixed number of
places with a negative zero folded into zero.

One feature, one entry
----------------------

A real export is long in one particular way. The survey reports a round only where the
triangles lie on one cylinder, so a rounded edge that bends - round the end of a web, round
the corner of a plate - comes back as a piece per step of the bend: the systainer handle's
1 mm round-overs are 142 partial rounds under five square millimetres, and a 45 degree
countersink is 24 flats of two triangles each, one per facet of the cone. Every piece is
measured and every piece is printed, but printing each on its own line says the same thing
a hundred times and buries the bores between them.

So pieces that are visibly one feature are written as one entry: a *run*. Partial rounds
are a run when each touches the next, the material is on the same side, their radii agree
to :data:`_DRIFT`, and their axes turn from one to the next - by more than :data:`FLAT`, or
the survey would have put them on one cylinder, and by no more than :data:`TURN`, the most
one facet of a round steps from the next. Flats are a run on the same terms with their
normals in place of axes and alike areas in place of alike radii. A run of three or more
prints once: how many pieces, their radius or lean, the area and box of all of them, and the
largest piece in full with its candidate; a run of one or two prints as the pieces it is,
because an entry that stands for two saves nothing. Nothing is dropped by size - a full
bore of a square millimetre is a bore and is never in a run - and every number on a run's
line is a sum, a least or a most over its pieces' own.

A threshold sits where real data falls
---------------------------------------

Three thresholds have needed patching after a real part landed exactly on the figure one
used: the survey's default section heights at multiples of h/6 (task-20), the thinnest-wall
rule's original 1% share of the surface (task-22, task-24), and :data:`_FILLET_TURN`'s exact
half turn (task-23). Each was chosen from a figure that reads naturally rather than one
argued from a real part's measurements, and a real part is drawn at exactly those natural
figures - so the boundary sat in the densest part of the data, not a sparse one.
``decision-5`` in ``backlog/decisions/`` names the pattern and the rule a new threshold must
satisfy: argue it from a measured distribution, as :data:`_DRIFT` below is argued from the
touching-pair radius histogram; and where the threshold decides *whether a reading is real*
rather than how it is shown, make it an absolute figure over the printed unit, never a share,
as :data:`LEAST` now gates the thinnest-wall reading and :data:`_TAIL` only decides how an
already-real reading is described.
"""

import math
from collections.abc import Callable
from typing import assert_never

from .geometry import TOL, Point, Vector
from .survey import (
    BAND,
    FLAT,
    LEAST,
    PLACE,
    SAME,
    TURN,
    Band,
    Flat,
    Outline,
    Repeat,
    Round,
    Section,
    Step,
    Survey,
    Walls,
)

_STRAIGHT = math.cos(math.radians(1.0))
"""How nearly a direction must line up with an axis to be called by its name: within a
degree. A face that leans more than that is described by its lean, in degrees."""

_SAME_SECTION = 0.05
"""How far, in millimetres, two sections' boxes may differ and still be the same section:
:data:`bench.survey.PLACE`, because a section read off a tessellation is only that good."""

_SAME_AREA = 0.005
"""How much, as a fraction, two sections' areas may differ and still be the same section."""

_TAIL = 0.01
"""The share of the measured surface below which a wall band is part of the tail: summed
into one line rather than listed, because a real export has hundreds of bands under a
square millimetre each and the reader wants the few that carry the surface."""

_STRIP = 0.5
"""The mean width, in millimetres, under which a flat is a strip rather than a face: its area
over the longest side of its box. On the systainer exports the facet strips left along a
fillet's edge are 0.08 to 0.49 mm wide and the narrowest real face is 0.5; a strip is flat
because a facet is, and is not offered as a face."""

_NO_AREA = 0.01
"""Below this, in square millimetres, an open run of a section encloses nothing: the plane
met the mesh along an edge or in a face rather than cutting through it, which is what a
height chosen at a round number does to a part drawn at round numbers."""

_DRIFT = 0.1
"""How far apart, in millimetres, the radii of two touching partial rounds may be and still
be pieces of one rounded edge. The survey's :data:`~bench.survey.SAME` (0.02) is how alike
two rounds must be to be the same *feature*; the pieces of a round-over that bends are not the
same cylinder and do not fit one that closely - on the systainer handle the pieces of one
1 mm round-over fit radii from 0.911 to 1.007 mm, and SAME would leave the 57 mm straight
stretch of an edge (radius 0.926 to 0.945) out of the run its own corner pieces (0.983 to
0.997) make. A tenth is twice :data:`~bench.topology.CHORD`, the slack the survey gathers a
round at before its axis is refitted, and on the three systainer exports every run it makes is
one rounded edge; two rounds that touch on parallel axes - the handle's 18 mm grip beside a
17.999 mm neighbour - are kept apart by the axis test, not by this one."""

_RUN = 3
"""How many pieces make a run worth one entry. Fewer print as the pieces they are: an entry
standing for two pieces is as long as the two."""

_INDENT = "  "
"""One level of indent, and the marker of a line that qualifies the one above it."""


def report(found: Survey) -> str:
    """``found`` as text a person can act on, built from the survey alone.

    One block per part of the survey - extent, sections, walls, flats, rounds, repeats - each
    a measured line followed by the candidate vocabulary that fits it, and a closing block of
    what was not measured. A part of the survey with nothing in it says so rather than
    disappearing, because "no rounds were found" is an answer too.
    """
    blocks = (
        _extent(found),
        _sections(found.sections),
        _walls(found.walls),
        _flats(found.flats),
        _rounds(found.rounds),
        _repeats(found.repeats),
        _limits(found),
    )
    return "\n\n".join(blocks) + "\n"


# ---- numbers ---------------------------------------------------------------------------


def _mm(x: float) -> str:
    """A length to a thousandth of a millimetre, with no negative zero."""
    return _fixed(x, 3)


def _mm2(x: float) -> str:
    """An area to a tenth of a square millimetre."""
    return _fixed(x, 1)


def _deg(radians: float) -> str:
    return _fixed(math.degrees(radians), 0)


def _pct(part: float, whole: float) -> str:
    return _fixed(100.0 * part / whole if whole > 0.0 else 0.0, 1)


def _fixed(x: float, places: int) -> str:
    text = f"{x:.{places}f}"
    # "-0.000" is what a rounded negative sliver prints as, and it is zero to this many places.
    return text[1:] if text.startswith("-") and text.strip("-0.") == "" else text


def _point(p: Point) -> str:
    return f"({_mm(p.x)}, {_mm(p.y)}, {_mm(p.z)})"


def _flat_point(p: Point) -> str:
    """A point on a section plane, which has only two coordinates worth printing."""
    return f"({_mm(p.x)}, {_mm(p.y)})"


def _vector(v: Vector) -> str:
    return f"Vector({_mm(v.x)}, {_mm(v.y)}, {_mm(v.z)})"


def _direction(v: Vector) -> str:
    """``+Z`` for a direction within a degree of an axis, or its three components."""
    for name, along in (
        ("X", Vector(1.0, 0.0, 0.0)),
        ("Y", Vector(0.0, 1.0, 0.0)),
        ("Z", Vector(0.0, 0.0, 1.0)),
    ):
        dot = v @ along
        if dot >= _STRAIGHT:
            return f"+{name}"
        if dot <= -_STRAIGHT:
            return f"-{name}"
    return f"({_mm(v.x)}, {_mm(v.y)}, {_mm(v.z)})"


def _along(v: Vector) -> bool:
    """Whether ``v`` lies within a degree of one of the three axes."""
    return not _direction(v).startswith("(")


def _size(low: Point, high: Point) -> Vector:
    return high - low


# ---- extent ----------------------------------------------------------------------------


def _extent(found: Survey) -> str:
    e = found.extent
    lines = [f"SURVEY of {found.triangles} triangles"]
    if found.triangles == 0:
        lines.append(f"{_INDENT}nothing to measure: the mesh has no triangles in it")
        return "\n".join(lines)
    lines.append(
        f"{_INDENT}extent {_mm(e.size.x)} x {_mm(e.size.y)} x {_mm(e.size.z)} mm, "
        f"from {_point(e.low)} to {_point(e.high)}"
    )
    lines.append(
        f"{_INDENT}candidate: cuboid({_mm(e.size.x)}, {_mm(e.size.y)}, {_mm(e.size.z)}, "
        f"at=Point{_point(e.low)}) is the box it fills; the body is somewhere inside that box"
    )
    lines.append(_legend())
    return "\n".join(lines)


# ---- sections --------------------------------------------------------------------------


def _sections(sections: tuple[Section, ...]) -> str:
    lines = ["SECTIONS"]
    if not sections:
        lines.append(f"{_INDENT}none taken: the body has no height to cut through")
        return "\n".join(lines)
    ordered = sorted(sections, key=lambda s: s.z)
    for section in ordered:
        outlines = _ordered_outlines([o for o in section.outlines if not _empty(o)])
        empty = sum(1 for o in section.outlines if _empty(o))
        count = len(outlines)
        noun = "outline" if count == 1 else "outlines"
        lines.append(f"{_INDENT}at z = {_mm(section.z)}: {count} {noun}")
        for outline in outlines:
            lines.append(f"{_INDENT * 2}{_outline(outline)}")
        if empty:
            runs = "run" if empty == 1 else "runs"
            lines.append(
                f"{_INDENT * 2}and {empty} {runs} enclosing no area: what a plane leaves where "
                "it meets the mesh along an edge or in a face instead of cutting through; this "
                "height lands on one, and survey(mesh, at=...) a little off it would not"
            )
        if count == 0 and not empty:
            lines.append(f"{_INDENT * 2}the plane at this height cuts nothing")
    lines.append(f"{_INDENT}{_straightness(ordered)}")
    return "\n".join(lines)


def _empty(o: Outline) -> bool:
    """A run that encloses nothing: a section's trace along the mesh, not through it."""
    return o.area < _NO_AREA


def _ordered_outlines(outlines: list[Outline]) -> list[Outline]:
    return sorted(outlines, key=lambda o: (-o.area, o.low.x, o.low.y, o.high.x, o.high.y))


def _outline(o: Outline) -> str:
    size = _size(o.low, o.high)
    text = (
        f"{_mm(size.x)} x {_mm(size.y)} mm from {_flat_point(o.low)}, enclosing {_mm2(o.area)} mm2"
    )
    if not o.closed:
        return (
            f"{text}; OPEN - its ends did not meet: the plane runs along an edge or a face of "
            "the mesh at this height, or the mesh has a gap; either way the area is not to be "
            "trusted"
        )
    return f"{text}, {_fills(o.area, size.x, size.y)}"


def _fills(area: float, w: float, d: float) -> str:
    """How much of its box an outline's area fills, beside what the sketch shapes fill - a
    fact about two numbers the reader compares, never a reading of the curve: a rounded_rect
    with small corners fills 99.7% of its box, and nothing here can tell it from a rect."""
    box = w * d
    if box <= TOL:
        return "with no box to fill"
    return f"filling {_pct(area, box)}% of its box"


def _legend() -> str:
    """What the sketch shapes fill of their own boxes, said once so every outline and flat can
    give its share and leave the comparison to the reader."""
    return (
        f"{_INDENT}a shape's share of its box: a rect fills 100.0%, a circle or an ellipse "
        f"{_pct(math.pi / 4.0, 1.0)}%, a rounded_rect somewhere between"
    )


def _straightness(sections: list[Section]) -> str:
    """Whether every section measured is the same section: the reading that tells a
    straight wall from a tapered one, and the fact an extrude() stands or falls on."""
    cut = [s for s in sections if any(not _empty(o) for o in s.outlines)]
    if len(cut) < 2:
        return "one height cut the body, so nothing says whether it is straight between heights"
    first = _ordered_outlines([o for o in cut[0].outlines if not _empty(o)])
    for section in cut[1:]:
        if not _same_outlines(
            first, _ordered_outlines([o for o in section.outlines if not _empty(o)])
        ):
            return (
                f"the sections differ between z = {_mm(cut[0].z)} and z = {_mm(cut[-1].z)}: "
                "the body is not one straight extrude() through these heights; a loft, a "
                "hull, or several bodies would be"
            )
    return (
        f"every height cut from z = {_mm(cut[0].z)} to z = {_mm(cut[-1].z)} is the same "
        f"section to within {_mm(_SAME_SECTION)} mm; candidate: one straight extrude() runs "
        "through these heights"
    )


def _same_outlines(a: list[Outline], b: list[Outline]) -> bool:
    if len(a) != len(b):
        return False
    for p, q in zip(a, b, strict=True):
        near = (
            abs(p.low.x - q.low.x) <= _SAME_SECTION
            and abs(p.low.y - q.low.y) <= _SAME_SECTION
            and abs(p.high.x - q.high.x) <= _SAME_SECTION
            and abs(p.high.y - q.high.y) <= _SAME_SECTION
            and abs(p.area - q.area) <= _SAME_AREA * max(p.area, q.area, TOL)
            and p.closed == q.closed
        )
        if not near:
            return False
    return True


# ---- walls -----------------------------------------------------------------------------


def _walls(walls: Walls | None) -> str:
    lines = ["WALLS"]
    if walls is None:
        lines.append(
            f"{_INDENT}no thickness measured: no ray from any triangle met a surface facing "
            "back, which is what an open mesh, or a mesh with no inside, leaves"
        )
        return "\n".join(lines)
    bands = sorted(walls.bands, key=lambda b: (-b.area, b.thickness))
    total = sum(b.area for b in bands)
    lines.append(f"{_INDENT}material under the surface, by the area that measured it:")
    shown = [b for b in bands if b.area >= _TAIL * total] or bands[:1]
    for band in shown:
        lines.append(
            f"{_INDENT * 2}{_mm(band.thickness)} mm under {_mm2(band.area)} mm2 "
            f"({_pct(band.area, total)}%)"
        )
    tail = bands[len(shown) :]
    if tail:
        thick = sorted(b.thickness for b in tail)
        rest = sum(b.area for b in tail)
        lines.append(
            f"{_INDENT * 2}and {len(tail)} more bands, {_mm(thick[0])} to {_mm(thick[-1])} mm, "
            f"each under {_pct(_TAIL, 1.0)}% of the surface, together {_mm2(rest)} mm2 "
            f"({_pct(rest, total)}%)"
        )
    if bands:
        lines.append(
            f"{_INDENT}candidate: a wall of {_mm(bands[0].thickness)} mm, the thickness the "
            "largest share of the surface measured"
        )
    lines.append(f"{_INDENT}{_thinnest(walls, bands, total)}")
    return "\n".join(lines)


def _thinnest(walls: Walls, bands: list[Band], total: float) -> str:
    """The single thinnest reading, beside the area that read anything like it - so a
    sliver off the tessellation is called one place, and only a wall is called a wall."""
    band = round(walls.thinnest / BAND) * BAND
    carrying = next((b for b in bands if abs(b.thickness - band) <= TOL), None)
    where = f"{_mm(walls.thinnest)} mm at {_point(walls.at)}"
    if carrying is None or carrying.area < LEAST:
        return (
            f"thinnest single reading: {where}, from one triangle; under a square millimetre "
            f"of surface read within {_mm(BAND / 2.0)} mm of it - less than the survey reports "
            "as a face - so this is one place, as a sliver of the tessellation leaves where two "
            "surfaces nearly meet, and not a wall; the bands above are where the material is. "
            "check_wall() reads this same number, and fails any least wall above it"
        )
    if carrying.area < _TAIL * total:
        return (
            f"thinnest single reading: {where}; {_mm2(carrying.area)} mm2 of surface "
            f"({_pct(carrying.area, total)}%) read within {_mm(BAND / 2.0)} mm of it - a thin "
            "place of that area, not one of the walls above, and the number check_wall() reads "
            "first"
        )
    return (
        f"thinnest single reading: {where}, in the {_mm(carrying.thickness)} mm band, which "
        f"{_mm2(carrying.area)} mm2 ({_pct(carrying.area, total)}%) of the surface measured; "
        "check_wall() measures this same reading"
    )


# ---- flats -----------------------------------------------------------------------------


def _flats(flats: tuple[Flat, ...]) -> str:
    lines = ["FLATS standing alone"]
    if not flats:
        lines.append(f"{_INDENT}none of a square millimetre or more that does not repeat")
        return "\n".join(lines)
    faces = [f for f in _ordered_flats(flats) if _fragment(f) is None]
    fragments = [f for f in _ordered_flats(flats) if _fragment(f) is not None]
    alone, runs = _runs(faces, _flats_run_on, _ordered_flats)
    for flat in alone:
        lines.extend(_INDENT + line for line in _flat_lines(flat))
    for run in runs:
        lines.extend(_INDENT + line for line in _flat_run_lines(run))
    if fragments:
        lines.append(f"{_INDENT}{_fragments(fragments)}")
    return "\n".join(lines)


# ---- runs: one feature in pieces -------------------------------------------------------


def _runs[T: Flat | Round](
    pieces: list[T],
    joined: Callable[[T, T], bool],
    ordered: Callable[[tuple[T, ...]], list[T]],
) -> tuple[list[T], list[list[T]]]:
    """``pieces`` split into the ones that stand alone and the runs of :data:`_RUN` or more
    that ``joined`` links, each run biggest piece first and the runs biggest first.

    A piece is in a run with any piece it joins, and with everything that one joins: three
    steps of a bend make one run whether or not the first step touches the last.
    """
    groups: list[list[T]] = []
    for piece in pieces:
        touching = [g for g in groups if any(joined(piece, other) for other in g)]
        if not touching:
            groups.append([piece])
            continue
        first, *rest = touching
        first.append(piece)
        for g in rest:
            first.extend(g)
            groups.remove(g)
    alone = ordered(tuple(p for g in groups if len(g) < _RUN for p in g))
    runs = [ordered(tuple(g)) for g in groups if len(g) >= _RUN]
    runs.sort(key=lambda run: (-sum(p.area for p in run), run[0].centre.x, run[0].centre.y))
    return alone, runs


def _touching(a: Flat | Round, b: Flat | Round) -> bool:
    """Whether two surfaces' boxes meet or overlap, to within :data:`PLACE`: pieces of one
    edge share their vertices, and a box read off a tessellation is only that good."""
    return (
        min(a.high.x, b.high.x) - max(a.low.x, b.low.x) >= -PLACE
        and min(a.high.y, b.high.y) - max(a.low.y, b.low.y) >= -PLACE
        and min(a.high.z, b.high.z) - max(a.low.z, b.low.z) >= -PLACE
    )


def _turned(a: Vector, b: Vector) -> bool:
    """Whether two directions, either way along, differ by more than :data:`FLAT` - so the
    survey did not read them as one - and by no more than :data:`TURN`, one facet's step."""
    dot = min(1.0, abs(a @ b))
    return math.cos(TURN) <= dot < math.cos(FLAT)


def _flats_run_on(a: Flat, b: Flat) -> bool:
    """Whether two flats are neighbouring facets of one faceted curve: touching, alike in
    area by the survey's own measure of the same feature, and facing a step apart."""
    return (
        _touching(a, b)
        and abs(a.area - b.area) <= SAME * max(1.0, math.sqrt(max(a.area, b.area)))
        and _turned(a.normal, b.normal)
    )


def _rounds_run_on(a: Round, b: Round) -> bool:
    """Whether two partial rounds are neighbouring pieces of one rounded edge: touching,
    material on the same side, radii within :data:`_DRIFT`, and axes turned a step. A full
    turn is a bore or a cylinder whatever it touches, and is never a piece of anything."""
    return (
        not _full(a.turn)
        and not _full(b.turn)
        and a.concave == b.concave
        and _touching(a, b)
        and abs(a.radius - b.radius) <= _DRIFT
        and _turned(a.axis, b.axis)
    )


def _box_of(pieces: list[Flat] | list[Round]) -> tuple[Point, Point]:
    return (
        Point(
            min(p.low.x for p in pieces), min(p.low.y for p in pieces), min(p.low.z for p in pieces)
        ),
        Point(
            max(p.high.x for p in pieces),
            max(p.high.y for p in pieces),
            max(p.high.z for p in pieces),
        ),
    )


def _rest_of(run: list[Flat] | list[Round], noun: str) -> str:
    rest = run[1:]
    return (
        f"and {len(rest)} more {noun}s, {_mm2(sum(p.area for p in rest))} mm2 between them, "
        f"the smallest {_mm2(rest[-1].area)} mm2"
    )


def _cone_axis(run: list[Flat]) -> tuple[str, float] | None:
    """The axis every flat of ``run`` leans from by the same angle, to within a degree, with
    that angle - the reading that makes a ring of facets a cone - or ``None``. A lean of
    ninety degrees is every normal perpendicular to the axis, which is a cylinder's facets
    and not a cone's, so it does not count; nor does no lean at all."""
    for name, part in (("+X", "x"), ("+Y", "y"), ("+Z", "z")):
        leans = [math.acos(min(1.0, abs(getattr(f.normal, part)))) for f in run]
        lean = sum(leans) / len(leans)
        alike = max(leans) - min(leans) <= math.radians(1.0)
        if alike and math.radians(1.0) <= lean <= math.radians(89.0):
            return name, lean
    return None


def _flat_run_lines(run: list[Flat]) -> list[str]:
    """A run of flats as one entry: what it is made of, then its largest piece in full."""
    low, high = _box_of(run)
    areas = sorted(f.area for f in run)
    cone = _cone_axis(run)
    if cone is not None:
        axis, lean = cone
        what = (
            f"every normal {_deg(lean)} degrees off {axis} and stepping round it - the facets "
            f"of a cone about {axis}, which the round test does not take"
        )
        offered = [
            f"{_INDENT}candidate: a cone about {axis} - the countersink or the chamfer of a "
            "hole() if it rings a bore, a loft() between two circles if it is a body's side"
        ]
    else:
        # Three 619 mm2 facets on the systainer handle are the coarse top of its grip; three
        # alike faces at shallow angles could as well be meant as facets, so neither is said.
        what = (
            "normals a step apart - one faceted surface, a curve too coarse for the round "
            "test or facets meant as they are"
        )
        offered = []
    return [
        f"{len(run)} flats in a run, {_mm2(areas[0])} to {_mm2(areas[-1])} mm2 each and each "
        f"touching the next with {what}: {_mm2(sum(areas))} mm2 in all, in a box {_point(low)} "
        f"to {_point(high)}; the largest:",
        *(_INDENT + line for line in _flat_lines(run[0])),
        f"{_INDENT}{_rest_of(run, 'flat')}",
        *offered,
    ]


def _ordered_flats(flats: tuple[Flat, ...]) -> list[Flat]:
    return sorted(flats, key=lambda f: (-f.area, f.centre.x, f.centre.y, f.centre.z))


def _width(f: Flat) -> float:
    """A flat's mean width: its area over the longest side of its box."""
    size = _size(f.low, f.high)
    return f.area / max(size.x, size.y, size.z, TOL)


def _fragment(f: Flat) -> str | None:
    """Why ``f`` is not offered as a face, or ``None`` when it is one.

    One triangle is flat whatever surface it belongs to, so a flat of one says nothing about
    the body; and a strip under :data:`_STRIP` wide is the facet a curve's tessellation
    leaves along an edge. On the systainer exports these are five in six of the flats a
    survey reports, and every one of them read as a face with a loft() beside it.
    """
    if f.facets == 1:
        return "one triangle, flat whatever surface it belongs to"
    if _width(f) < _STRIP:
        return f"a strip {_mm(_width(f))} mm wide on average, as a facet of a curve is"
    return None


def _fragments(fragments: list[Flat]) -> str:
    """The flats that are not faces, in one line: how many, how much surface, the largest."""
    single = sum(1 for f in fragments if f.facets == 1)
    strips = len(fragments) - single
    parts = []
    if single:
        parts.append(f"{single} of one triangle each")
    if strips:
        parts.append(f"{strips} {'strip' if strips == 1 else 'strips'} under {_mm(_STRIP)} mm wide")
    biggest = fragments[0]
    return (
        f"and {len(fragments)} more flats not offered as faces - {' and '.join(parts)}, "
        f"{_mm2(sum(f.area for f in fragments))} mm2 in all, the largest {_mm2(biggest.area)} "
        f"mm2 at {_point(biggest.centre)}: one triangle is flat whatever surface it belongs "
        "to, and a strip is the facet a curve's tessellation leaves along an edge"
    )


def _flat_lines(f: Flat) -> list[str]:
    """A flat as a measured line and the candidate that fits it - or, for a flat that is not
    a face, the reason none is offered."""
    size = _size(f.low, f.high)
    facing = _direction(f.normal)
    facets = f"{f.facets} facet" if f.facets == 1 else f"{f.facets} facets"
    why = _fragment(f)
    if facing in ("+Z", "-Z"):
        up = "up" if facing == "+Z" else "down"
        measured = (
            f"facing {facing} ({up}) at z = {_mm(f.centre.z)}: {_mm(size.x)} x {_mm(size.y)} mm "
            f"from {_flat_point(f.low)}, {_mm2(f.area)} mm2 "
            f"{_fills(f.area, size.x, size.y)}, centre {_point(f.centre)}, {facets}"
        )
        offered = (
            f"candidate: an outline drawn on raised(XY, {_mm(f.centre.z)}) - a top or "
            f"a bottom of an extrude(), the crown of a boss(), the floor of a pocket()"
        )
    elif facing in ("+X", "-X", "+Y", "-Y"):
        if facing[1] == "X":
            across, along, start, at = "y", size.y, f.low.y, f.centre.x
        else:
            across, along, start, at = "x", size.x, f.low.x, f.centre.y
        measured = (
            f"facing {facing} at {facing[1].lower()} = {_mm(at)}: {_mm(along)} mm along "
            f"{across} from {across} = {_mm(start)}, {_mm(size.z)} mm tall from "
            f"z = {_mm(f.low.z)}, {_mm2(f.area)} mm2 {_fills(f.area, along, size.z)}, "
            f"centre {_point(f.centre)}, {facets}"
        )
        offered = (
            f"candidate: a straight side of an extrude() - one edge of its outline "
            f'swept {_mm(size.z)} mm; plane_of(body, "side-...") is how a sketch reaches it'
        )
    else:
        lean = math.acos(max(-1.0, min(1.0, abs(f.normal.z))))
        measured = (
            f"facing {facing}, {_deg(lean)} degrees off horizontal: {_mm2(f.area)} mm2 in a "
            f"{_mm(size.x)} x {_mm(size.y)} x {_mm(size.z)} mm box from {_point(f.low)}, "
            f"centre {_point(f.centre)}, {facets}"
        )
        offered = (
            "candidate: a face that leans is a loft() between two outlines, or a hull() "
            "of the slices it runs between; no single extrude() has one"
        )
    if why is not None:
        offered = f"no candidate: {why}"
    return [measured, f"{_INDENT}{offered}"]


# ---- rounds ----------------------------------------------------------------------------


def _rounds(rounds: tuple[Round, ...]) -> str:
    lines = ["ROUNDS standing alone"]
    if not rounds:
        lines.append(f"{_INDENT}none of a square millimetre or more that does not repeat")
        return "\n".join(lines)
    alone, runs = _runs(list(rounds), _rounds_run_on, _ordered_rounds)
    for one in alone:
        lines.extend(_INDENT + line for line in _round_lines(one))
    for run in runs:
        lines.extend(_INDENT + line for line in _round_run_lines(run))
    if any(not _full(r.turn) for r in rounds):
        lines.append(
            f"{_INDENT}bench has no fillet verb: a fillet is a hull() of slices, or a profile "
            "drawn with the round in it and extruded"
        )
    return "\n".join(lines)


def _ordered_rounds(rounds: tuple[Round, ...]) -> list[Round]:
    return sorted(rounds, key=lambda r: (-r.area, r.centre.x, r.centre.y, r.centre.z))


def _full(turn: float) -> bool:
    return turn >= 2.0 * math.pi - TOL


def _round_run_lines(run: list[Round]) -> list[str]:
    """A run of partial rounds as one entry: a rounded edge in pieces, then its largest
    piece in full. The pieces' axes turn from one to the next, which is what a round-over
    leaves where the edge it follows bends - or, when the pieces are convex, what a bent rod
    leaves; which, the reader says. A concave run is never offered as a rod - material is
    outside it, the same reading :func:`_partial_candidate` gives one piece on its own.
    Their radii agree only loosely, because no piece is quite the cylinder it is fitted as,
    so the radius is given as the range the pieces span."""
    low, high = _box_of(run)
    radii = sorted(r.radius for r in run)
    longest = max(run, key=lambda r: (r.length, -r.area))
    side = "concave, material outside it" if run[0].concave else "convex, material inside it"
    bends = (
        "what a rounded edge leaves where it bends or its radius drifts - never a rod, "
        "material is outside it"
        if run[0].concave
        else "what a rounded edge leaves where it bends or its radius drifts, or a bent rod"
    )
    return [
        f"round-over in {len(run)} pieces: radius {_mm(radii[0])} to {_mm(radii[-1])} mm, "
        f"{side}, each piece touching the next and turned from it - {bends}: "
        f"{_mm2(sum(r.area for r in run))} "
        f"mm2 in all, the longest piece {_mm(longest.length)} mm along "
        f"{_direction(longest.axis)}, in a box {_point(low)} to {_point(high)}; the largest:",
        *(_INDENT + line for line in _round_lines(run[0])),
        f"{_INDENT}{_rest_of(run, 'piece')}",
    ]


def _round_lines(r: Round) -> list[str]:
    """A round as a measured line and the candidate that fits it. A full turn facing in is
    a bore and facing out a cylinder. A partial turn about X, Y or Z but not vertical is a
    corner or a fillet, whichever concave and turn allow: convex is a rod or a bar going on
    round, or a fillet or an eased edge rounding a corner - a rod is never offered concave,
    because material is outside it. A concave turn near a full circle - :data:`_BORE_TURN` or
    more - is a bore something has opened into, not a fillet at any width; between that and
    :data:`_FILLET_TURN` neither reading is warranted and none is offered."""
    axis = _direction(r.axis)
    facets = f"{r.facets} facet" if r.facets == 1 else f"{r.facets} facets"
    fit = f"vertices within {_mm(r.spread)} mm of the radius"
    side = "concave, material outside it" if r.concave else "convex, material inside it"
    if _full(r.turn):
        kind = "bore" if r.concave else "cylinder"
        measured = (
            f"{kind}: diameter {_mm(2.0 * r.radius)} mm (radius {_mm(r.radius)}), axis {axis}, "
            f"{_mm(r.length)} mm long, centre {_point(r.centre)}, {side}, full circle, {fit}, "
            f"{_mm2(r.area)} mm2, {facets}"
        )
        return [measured, f"{_INDENT}{_full_candidate(r, axis)}"]
    measured = (
        f"partial round: radius {_mm(r.radius)} mm over {_deg(r.turn)} degrees, axis {axis}, "
        f"{_mm(r.length)} mm long, {side}, box {_point(r.low)} to {_point(r.high)}, {fit}, "
        f"{_mm2(r.area)} mm2, {facets}"
    )
    return [measured, f"{_INDENT}{_partial_candidate(r, axis)}"]


def _full_candidate(r: Round, axis: str) -> str:
    foot = r.centre - r.axis * (r.length / 2.0)
    if r.concave:
        text = (
            f"candidate: hole(body, ..., diameter={_mm(2.0 * r.radius)}, depth={_mm(r.length)}) "
            f"on its axis through {_point(r.centre)}"
        )
        if not _along(r.axis):
            text += (
                "; the axis is not along X, Y or Z, and hole() takes the plane it is drilled "
                "from as on=, which is where that lean is written"
            )
        return text
    text = f"candidate: cylinder({_mm(r.radius)}, {_mm(r.length)}, at=Point{_point(foot)})"
    if axis != "+Z":
        text += f" turned to stand along {axis}"
    return f"{text}; or a boss() of circle({_mm(r.radius)}) the same height"


_FILLET_TURN = math.pi
"""The most a concave partial round may turn and still be offered as an inside fillet or an
eased edge rounding a corner: half a circle, the same figure the axis-along-Z corner wording
already uses for the far end of what a rounded profile does - a quarter turn is one corner, a
half turn is the end of a slot(). A concave surface is never a rod (material is outside it),
so past this the fillet reading is the only one at stake, and past a full half-turn nothing
that rounds a corner is left to call it.

Known limit, accepted rather than fixed (task-23, decision-5): two real pieces on the
systainer handle both print as "180 degrees" under :func:`_deg`'s fixed-place rounding but
land on opposite sides of this threshold, because their true turns differ by less than a
degree - the amount :func:`_deg` does not carry. One line reads the fillet candidate, its
neighbour reads "no candidate", and each is correct for what it measured. No alternative
figure for this threshold survived task-23's search of the handle's own data, and widening
:func:`_deg`'s precision would change every degree reading in the report, not just this one -
so the boundary stays here and the split is disclosed rather than hidden."""

_BORE_TURN = math.radians(270.0)
"""How much of a circle a concave partial round must cover before the report reads it as a
bore something has opened into. The systainer handle's own two rounds - a 4 mm bore opened
along one side by a slot - measure 345 degrees, missing 15: a circle short a narrow gap, not
a corner rounded by anything. Between :data:`_FILLET_TURN` and here (180 to 270 degrees, a
missing arc of 90 to 180 degrees) neither reading is warranted - not little enough missing to
call it a bore something narrow opened, not little enough turn to call it a corner - and per
task-23 the report says less rather than choosing."""


def _partial_candidate(r: Round, axis: str) -> str:
    if axis in ("+Z", "-Z"):
        corner = "an inside corner" if r.concave else "an outside corner"
        return (
            f"candidate: {corner} of a rounded_rect(..., {_mm(r.radius)}) extruded "
            f"{_mm(r.length)} mm; a quarter turn is one corner, a half turn is the end of a "
            "slot()"
        )
    if not r.concave:
        return (
            f"candidate: {_deg(r.turn)} degrees of a cylinder of diameter {_mm(2.0 * r.radius)} "
            f"lying along {axis} - a rod or a bar if the surface goes on round, a fillet or an "
            "eased edge if it rounds a corner"
        )
    if r.turn >= _BORE_TURN:
        gap = _deg(2.0 * math.pi - r.turn)
        return (
            f"candidate: {_deg(r.turn)} degrees of a bore of diameter {_mm(2.0 * r.radius)} "
            f"lying along {axis}, missing {gap} degrees - hole(...) with a slot or a wall "
            "opened into it along the missing arc; material is outside it, so it is never a "
            "rod or a bar"
        )
    if r.turn > _FILLET_TURN:
        return (
            f"no candidate: {_deg(r.turn)} degrees of a concave cylinder of diameter "
            f"{_mm(2.0 * r.radius)} lying along {axis} is too much arc to call a fillet or an "
            "eased edge and not little enough missing to be sure it is a bore something has "
            "opened into; the measurement above is all this is"
        )
    return (
        f"candidate: {_deg(r.turn)} degrees of a concave cylinder of diameter "
        f"{_mm(2.0 * r.radius)} lying along {axis} - a fillet or an eased edge rounding a "
        "corner; material is outside it, so it is never a rod or a bar"
    )


# ---- repeats ---------------------------------------------------------------------------


def _repeats(repeats: tuple[Repeat, ...]) -> str:
    lines = ["REPEATS"]
    if not repeats:
        lines.append(f"{_INDENT}none: no three identical surfaces on one regular spacing")
        return "\n".join(lines)
    for repeat in _ordered_repeats(repeats):
        lines.extend(_INDENT + line for line in _repeat_lines(repeat))
    lines.append(
        f"{_INDENT}each repeat is one surface: a feature with several surfaces - a boss and "
        "its crown - is listed once per surface, on the same spacing"
    )
    return "\n".join(lines)


def _count(r: Repeat) -> int:
    return math.prod(s.count for s in r.steps)


def _ordered_repeats(repeats: tuple[Repeat, ...]) -> list[Repeat]:
    return sorted(
        repeats,
        key=lambda r: (-_count(r), -r.one.area, r.one.centre.x, r.one.centre.y, r.one.centre.z),
    )


def _repeat_lines(r: Repeat) -> list[str]:
    steps = sorted(r.steps, key=lambda s: (-s.count, abs(s.along), s.along.x, s.along.y, s.along.z))
    if len(steps) == 1:
        (step,) = steps
        head = (
            f"{step.count} in a row, {_mm(abs(step.along))} mm apart along "
            f"{_direction(step.along / abs(step.along))}, the first one:"
        )
        verb = f"candidate: pattern(one, {step.count}, {_vector(step.along)})"
    elif _one_line(*steps):
        a, b = steps
        head = _collinear(a, b)
        verb = (
            f"candidate: grid(one, ({a.count}, {b.count}), ({_vector(a.along)}, "
            f"{_vector(b.along)})) - grid() takes two steps along one line as readily as two "
            "across, and puts the copies at those offsets"
        )
    else:
        a, b = steps
        head = (
            f"{a.count} x {b.count} grid, {_mm(abs(a.along))} mm apart along "
            f"{_direction(a.along / abs(a.along))} and {_mm(abs(b.along))} mm along "
            f"{_direction(b.along / abs(b.along))}, the first one:"
        )
        verb = (
            f"candidate: grid(one, ({a.count}, {b.count}), ({_vector(a.along)}, "
            f"{_vector(b.along)}))"
        )
    match r.one:
        case Flat():
            body = _flat_lines(r.one)
        case Round():
            body = _round_lines(r.one)
        case _:
            assert_never(r.one)
    return [head, *(_INDENT + line for line in body), f"{_INDENT}{verb}, with one as above"]


def _one_line(a: Step, b: Step) -> bool:
    """Whether two steps lie along one line, to within a degree, either way along."""
    return abs((a.along / abs(a.along)) @ (b.along / abs(b.along))) >= _STRAIGHT


def _collinear(a: Step, b: Step) -> str:
    """Two steps along one line, said as what they place: groups of ``a`` along it, the
    groups ``b`` apart, and every offset from the first one - so a reader who did not
    measure the part sees four places on a line and not a grid that is not there.

    The survey found two rows sharing a step, offset from each other by a second step, and
    that is a lattice whichever way the second step points; the base plate's foot sockets
    sit at 0, 60, 121.5 and 181.5 mm along Y, which is two pairs 60 apart with the pairs
    121.5 apart, and ``grid(one, (2, 2), (Y * 60, Y * 121.5))`` puts them exactly there.
    """
    along = b.along / abs(b.along)
    offsets = sorted(
        {
            i * (a.along @ along) + j * (b.along @ along)
            for i in range(a.count)
            for j in range(b.count)
        }
    )
    places = ", ".join(_mm(o) for o in offsets[:-1]) + f" and {_mm(offsets[-1])}"
    return (
        f"{a.count * b.count} on one line along {_direction(along)}, in {b.count} groups of "
        f"{a.count}: {_mm(abs(a.along))} mm apart within a group and the groups "
        f"{_mm(abs(b.along))} mm apart, at {places} mm from the first one:"
    )


# ---- what was not measured -------------------------------------------------------------


def _limits(found: Survey) -> str:
    """What the survey cannot see and what it does not claim, so a reader does not fill the
    gaps in from the report's silence."""
    listed = sum(f.facets for f in found.flats) + sum(r.facets for r in found.rounds)
    listed += sum(r.one.facets for r in found.repeats)
    lines = ["NOT MEASURED"]
    if found.triangles > 0:
        lines.append(
            f"{_INDENT}the surfaces above account for {listed} of {found.triangles} triangles "
            f"({_pct(listed, found.triangles)}%; a repeat counted once); the rest did not "
            "measure as a flat or a round of a square millimetre or more, and nothing is said "
            "of them - a cone, a chamfer, a blend or a spline would fall there"
        )
    lines.extend(
        (
            f"{_INDENT}intent: a diameter is a diameter and a gap is a distance; which screw, "
            "fit or nominal asked for either is not in the mesh and is not claimed here",
            f"{_INDENT}names: a mesh carries no refs; every name in a script for this body is "
            "the writer's",
            f"{_INDENT}curves that are not cylinders - a spline, a fillet whose radius changes, "
            "a bend - come back as partial rounds of slightly different radius, written above "
            "as a round-over in pieces where they touch and turn, as flats of one triangle "
            "each, or not at all",
            f"{_INDENT}a taper is read only as sections that differ; a cone's surface is not "
            "reported as a round, and comes back, if at all, as a run of flats",
        )
    )
    return "\n".join(lines)
