"""Functional: task-71's eased rim, through the public vocabulary with no kernel.

:func:`bench.library.print.rim` generalises :func:`~bench.library.print.eased`: a top or a
bottom, rounded or chamfered, by a stack of hulled slices. Nothing here is evaluated - there
is no kernel and no mesh - so what is asserted is the tree's own promises: the bounding box
:func:`~bench.topology.bounds` reads straight off the recipe, the refs
:func:`~bench.model.index` hands out before anything is built, and the arguments the two
functions refuse. What only a real body can answer - which of those promised refs a union
actually keeps once an eased cap's base face is internal to it, and which way a round rim
overhangs - is ``tests/adapter/test_rim_measured.py``'s.
"""

from typing import Literal

import pytest

from bench import (
    Face,
    Point,
    X,
    Z,
    chamfer,
    circle,
    face,
    fill,
    fillet,
    plane,
    polygon,
    rect,
)
from bench.library.print import eased, rim
from bench.model import index
from bench.topology import Hull, Union, bounds

pytestmark = pytest.mark.functional

_R = 5.0
_LENGTH, _LEAD, _DROP = 20.0, 1.0, 2.0


def _profile() -> Face:
    return fill(circle(_R), on=plane(Point(0.0, 0.0, 0.0), Z, X))


def test_eased_is_rim_chamfered_both_ends() -> None:
    """The one case task-71 found already in the vocabulary - the function every existing
    script and check reads - is now :func:`rim` called this one way, so the two must build
    the identical extent whatever they are handed."""
    old = eased(_profile(), _LENGTH, lead=_LEAD, drop=_DROP)
    new = rim(_profile(), _LENGTH, lead=_LEAD, drop=_DROP, style="chamfer", top=True, bottom=True)
    assert bounds(old) == bounds(new)


def test_rim_with_neither_end_asked_for_is_refused() -> None:
    with pytest.raises(ValueError, match="top or bottom"):
        rim(_profile(), _LENGTH, lead=_LEAD, drop=_DROP, top=False, bottom=False)


@pytest.mark.parametrize(
    ("length", "lead", "drop"), [(0.0, 1.0, 1.0), (10.0, 0.0, 1.0), (10.0, 1.0, 0.0)]
)
def test_rim_needs_positive_numbers(length: float, lead: float, drop: float) -> None:
    with pytest.raises(ValueError):
        rim(_profile(), length, lead=lead, drop=drop)


def test_rim_refuses_two_eased_ends_that_meet_or_cross() -> None:
    """``drop`` twice over on both ends leaves no straight run between them at all - the
    two eased caps would have to overlap to reach the length asked for."""
    with pytest.raises(ValueError, match="meet or cross"):
        rim(_profile(), 10.0, lead=1.0, drop=6.0, top=True, bottom=True)


_NOTCHED = polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(5, 5), Point(0, 10)))
"""A square with a V cut into its top: one reflex corner, at ``(5, 5)``."""


@pytest.mark.parametrize(
    "profile",
    [
        fill(_NOTCHED),
        fill(fillet(_NOTCHED, 1.0, at=2)),
        fill(fillet(_NOTCHED, 1.0)),
    ],
    ids=["notched", "notch-filleted", "every-corner-filleted"],
)
@pytest.mark.parametrize("style", ["chamfer", "round"])
def test_rim_refuses_a_concave_outline_rather_than_filling_it_in(
    profile: Face, style: Literal["round", "chamfer"]
) -> None:
    """A hull of each slice would be the notch filled in, so the rim is refused - round or
    chamfered, and however the notch's corner itself was drawn."""
    with pytest.raises(ValueError, match="concave"):
        rim(profile, _LENGTH, lead=_LEAD / 4, drop=_DROP, style=style)


def test_rim_refuses_a_profile_with_a_hole() -> None:
    ring = face(rect(20, 20, Point(-10, -10)), holes=(circle(3.0),))
    with pytest.raises(ValueError, match="hole"):
        rim(ring, _LENGTH, lead=_LEAD, drop=_DROP)
    with pytest.raises(ValueError, match="hole"):
        eased(ring, _LENGTH, lead=_LEAD, drop=_DROP)


def test_rim_takes_a_convex_outline_with_rounded_and_cut_corners() -> None:
    """What the check must not refuse: eased_bracket's own plate, two corners filleted and
    two chamfered - convex all the way round, arcs and all."""
    outline = fillet(chamfer(rect(40, 30), 3.0, at=(2, 3)), 5.0, at=(0, 1))
    assert bounds(rim(fill(outline), 8.0, lead=1.2, drop=0.9, style="round", bottom=False))


def test_rim_round_needs_at_least_two_steps() -> None:
    with pytest.raises(ValueError, match="steps"):
        rim(_profile(), _LENGTH, lead=_LEAD, drop=_DROP, style="round", steps=1)


def test_rim_promises_top_and_bottom_before_anything_is_built() -> None:
    """:func:`~bench.model.index` reads the tree, not a mesh: it hands out ``top`` and
    ``bottom`` on both an eased end and a flat one alike, because the naming rule does not
    know which internal face a real boolean will remove. What survives once there is a
    kernel to ask is narrower - ``tests/adapter/test_rim_measured.py``."""
    both = rim(_profile(), _LENGTH, lead=_LEAD, drop=_DROP, style="round", top=True, bottom=True)
    assert {"top", "bottom", "side-0"} <= set(index(both))


def test_rim_keeps_the_straight_runs_own_extent() -> None:
    """The extent :func:`~bench.topology.bounds` reads off the recipe is the full profile's,
    at both ends - an eased rim never reaches past the size it was drawn at, only in from
    it - whichever end is asked for."""
    one_end = rim(
        _profile(), _LENGTH, lead=_LEAD, drop=_DROP, style="round", top=True, bottom=False
    )
    b = bounds(one_end)
    assert (b.x0, b.y0, b.z0, b.x1, b.y1, b.z1) == pytest.approx((-_R, -_R, 0.0, _R, _R, _LENGTH))


def _hull_count(node: object) -> int:
    """How many :class:`~bench.topology.Hull` nodes a recipe holds - one hulled segment
    between each pair of consecutive slices, whether a script's own or an eased cap's."""
    match node:
        case Hull():
            return 1
        case Union(a, b):
            return _hull_count(a.node) + _hull_count(b.node)
        case _:
            return 0


def test_rim_round_hulls_one_segment_per_step() -> None:
    """A round rim is a chain of ``steps`` hulled slices, the same technique a straight
    chamfer already used at ``steps=1`` in effect - two slices, one hull - generalised:
    more steps for a rim large enough that eight would show as facets."""
    for steps in (2, 5, 12):
        one_end = rim(
            _profile(),
            _LENGTH,
            lead=_LEAD,
            drop=_DROP,
            style="round",
            top=True,
            bottom=False,
            steps=steps,
        )
        assert _hull_count(one_end.node) == steps


def test_rim_chamfer_hulls_a_single_segment() -> None:
    """A chamfer is the two end slices of the stack and nothing between them: one hulled
    segment per eased end, whatever ``steps`` is asked for - it is read only by a round."""
    both = rim(_profile(), _LENGTH, lead=_LEAD, drop=_DROP, style="chamfer", top=True, bottom=True)
    assert _hull_count(both.node) == 2


def test_rim_is_new_beside_eased_in_the_print_domains_barrel() -> None:
    """A drift guard on ``__all__``, since :func:`rim` is new beside :func:`eased`."""
    from bench.library import print as print_domain

    assert {"rim", "eased"} <= set(print_domain.__all__)
    assert callable(print_domain.rim)
