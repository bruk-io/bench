"""Triangulate: a flat region with holes in it, as triangles.

A plate's top and bottom are a face's region, and a screen draws a region as triangles. This
is ear clipping: each hole is first joined to the outline by a bridge - a cut from the hole's
rightmost corner to a corner of the outline it can see - so the region becomes one polygon
walked once, and then a corner whose triangle holds nothing else is clipped off, again and
again, until one triangle is left (Eberly, *Triangulation by Ear Clipping*).

Plain arithmetic on ``(u, v)`` points; it imports nothing of bench's. It never raises: what is
too small or too broken to have an inside comes back as no triangles, and a region the clipping
cannot finish cleanly is finished anyway, one best corner at a time, so a plate is always drawn.
"""

import math
from collections.abc import Sequence

Point = tuple[float, float]
Triangle = tuple[int, int, int]

_EPS = 1e-9
"""Below this - a length in millimetres, or an area in square millimetres - two things are
the same and three points are in a line."""


def signed_area(points: Sequence[Point]) -> float:
    """The area ``points`` enclose, positive when they run counter-clockwise."""
    total = 0.0
    count = len(points)
    for k in range(count):
        x0, y0 = points[k]
        x1, y1 = points[(k + 1) % count]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def triangles(outer: Sequence[Point], holes: Sequence[Sequence[Point]] = ()) -> list[Triangle]:
    """The region inside ``outer`` and outside every hole, as counter-clockwise triangles.

    A triangle names its corners by where they stand in ``outer`` followed by each hole in
    turn, so the caller's own list of points - outline first, holes after - is what the
    numbers index. Either ring may run either way round, and a ring of fewer than three
    distinct corners, or of no area, is not a ring: an outline like that has no inside, and a
    hole like that cuts nothing.
    """
    rings = (outer, *holes)
    points: list[Point] = [point for ring in rings for point in ring]
    spans: list[list[int]] = []
    start = 0
    for ring in rings:
        spans.append(list(range(start, start + len(ring))))
        start += len(ring)

    shell = _cleaned(points, spans[0])
    if len(shell) < 3 or abs(_area(points, shell)) <= _EPS:
        return []
    if _area(points, shell) < 0.0:
        shell.reverse()

    cuts: list[list[int]] = []
    for span in spans[1:]:
        hole = _cleaned(points, span)
        if len(hole) < 3 or abs(_area(points, hole)) <= _EPS:
            continue
        if _area(points, hole) > 0.0:
            hole.reverse()
        cuts.append(hole)
    # Rightmost hole first, so each bridge reaches an outline no later hole's bridge crosses.
    cuts.sort(key=lambda hole: max(points[one][0] for one in hole), reverse=True)
    for hole in cuts:
        shell = _bridged(points, shell, hole)
    return _clipped(points, shell)


# ---- rings -------------------------------------------------------------------------------


def _cross(a: Point, b: Point, c: Point) -> float:
    """Twice the signed area of ``a, b, c``: positive when they turn left."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _same(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= _EPS and abs(a[1] - b[1]) <= _EPS


def _area(points: Sequence[Point], ring: Sequence[int]) -> float:
    return signed_area([points[one] for one in ring])


def _cleaned(points: Sequence[Point], ring: Sequence[int]) -> list[int]:
    """``ring`` without a corner that repeats the one before it, or that stands in a line
    between its neighbours - neither encloses anything, and both stop an ear being found."""
    kept: list[int] = []
    for one in ring:
        if not kept or not _same(points[kept[-1]], points[one]):
            kept.append(one)
    while len(kept) > 1 and _same(points[kept[0]], points[kept[-1]]):
        kept.pop()
    while len(kept) >= 3:
        count = len(kept)
        straight = [
            k
            for k in range(count)
            if abs(_cross(points[kept[k - 1]], points[kept[k]], points[kept[(k + 1) % count]]))
            <= _EPS
        ]
        if not straight:
            break
        # One at a time, so a run of corners in a line keeps the two that end it.
        kept.pop(straight[0])
    return kept


# ---- bridges -----------------------------------------------------------------------------


def _bridged(points: Sequence[Point], shell: list[int], hole: list[int]) -> list[int]:
    """``shell`` with ``hole`` joined into it along a bridge both ends of which can see each
    other, walked out along the bridge, once round the hole and back."""
    at = max(range(len(hole)), key=lambda k: (points[hole[k]][0], -points[hole[k]][1]))
    mx, my = points[hole[at]]
    seen = _seen_corner(points, shell, (mx, my))
    if seen is None:
        return shell  # a hole outside the outline cuts nothing
    around = hole[at:] + hole[:at]
    return shell[: seen + 1] + around + [hole[at], shell[seen]] + shell[seen + 1 :]


def _seen_corner(points: Sequence[Point], shell: Sequence[int], m: Point) -> int | None:
    """Where in ``shell`` the corner is that a bridge from ``m`` goes to.

    A ray from ``m`` towards +X meets the nearest edge of the outline; the end of that edge
    furthest along the ray can see ``m`` unless a reflex corner of the outline stands in the
    triangle between them, in which case the reflex corner nearest the ray's direction can.
    """
    mx, my = m
    count = len(shell)
    nearest = math.inf
    edge: int | None = None
    for k in range(count):
        a = points[shell[k]]
        b = points[shell[(k + 1) % count]]
        if (a[1] - my) * (b[1] - my) > 0.0 or abs(a[1] - b[1]) <= _EPS:
            continue
        x = a[0] + (my - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        if mx - _EPS <= x < nearest:
            nearest, edge = x, k
    if edge is None:
        return None
    a_at, b_at = edge, (edge + 1) % count
    candidate = a_at if points[shell[a_at]][0] > points[shell[b_at]][0] else b_at
    hit = (nearest, my)
    p = points[shell[candidate]]
    if _same(p, hit):
        return candidate

    best = candidate
    best_key = (_slope(m, p), math.dist(m, p))
    for k in range(count):
        if k == candidate:
            continue
        here = points[shell[k]]
        before = points[shell[k - 1]]
        after = points[shell[(k + 1) % count]]
        if _cross(before, here, after) > _EPS:
            continue  # a convex corner cannot hide the candidate
        if here[0] < mx - _EPS or not _inside(here, m, hit, p):
            continue
        key = (_slope(m, here), math.dist(m, here))
        if key < best_key:
            best, best_key = k, key
    return best


def _slope(m: Point, p: Point) -> float:
    """How far off the +X ray from ``m`` the point ``p`` lies, as the ray sees it."""
    dx = p[0] - m[0]
    return math.inf if dx <= _EPS else abs(p[1] - m[1]) / dx


def _inside(p: Point, a: Point, b: Point, c: Point) -> bool:
    """Whether ``p`` is inside the triangle ``a, b, c`` or on its edges, whichever way round
    the triangle runs."""
    d1, d2, d3 = _cross(a, b, p), _cross(b, c, p), _cross(c, a, p)
    negative = d1 < -_EPS or d2 < -_EPS or d3 < -_EPS
    positive = d1 > _EPS or d2 > _EPS or d3 > _EPS
    return not (negative and positive)


# ---- ears --------------------------------------------------------------------------------


def _clipped(points: Sequence[Point], polygon: Sequence[int]) -> list[Triangle]:
    """One simple counter-clockwise polygon - holes already bridged in - as triangles."""
    count = len(polygon)
    if count < 3:
        return []
    before = [(k - 1) % count for k in range(count)]
    after = [(k + 1) % count for k in range(count)]
    out: list[Triangle] = []
    left = count
    k = 0
    stalled = 0
    while left > 3:
        p, q = before[k], after[k]
        if stalled > left:
            # A whole lap with no ear: rounding has left no corner that passes cleanly.
            # Clip the corner that turns left the most, so the region still gets drawn.
            k = _sharpest(points, polygon, before, after, k, left)
            p, q = before[k], after[k]
        elif not _is_ear(points, polygon, before, after, p, k, q):
            k = q
            stalled += 1
            continue
        a, b, c = points[polygon[p]], points[polygon[k]], points[polygon[q]]
        if _cross(a, b, c) > _EPS:
            out.append((polygon[p], polygon[k], polygon[q]))
        after[p], before[q] = q, p
        left -= 1
        stalled = 0
        k = p
    p, q = before[k], after[k]
    a, b, c = points[polygon[p]], points[polygon[k]], points[polygon[q]]
    if _cross(a, b, c) > _EPS:
        out.append((polygon[p], polygon[k], polygon[q]))
    return out


def _is_ear(
    points: Sequence[Point],
    polygon: Sequence[int],
    before: Sequence[int],
    after: Sequence[int],
    p: int,
    k: int,
    q: int,
) -> bool:
    a, b, c = points[polygon[p]], points[polygon[k]], points[polygon[q]]
    if _cross(a, b, c) <= _EPS:
        return False
    j = after[q]
    while j != p:
        here = points[polygon[j]]
        # A bridge walks through the same corner twice; that corner is not in its own ear.
        if not (_same(here, a) or _same(here, b) or _same(here, c)) and _inside(here, a, b, c):
            return False
        j = after[j]
    return True


def _sharpest(
    points: Sequence[Point],
    polygon: Sequence[int],
    before: Sequence[int],
    after: Sequence[int],
    k: int,
    left: int,
) -> int:
    best, best_turn = k, -math.inf
    j = k
    for _ in range(left):
        turn = _cross(points[polygon[before[j]]], points[polygon[j]], points[polygon[after[j]]])
        if turn > best_turn:
            best, best_turn = j, turn
        j = after[j]
    return best
