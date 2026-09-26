"""Compare two ways of sweeping a profile: ``uv run python -m tools.sweep_routes``.

The modeller has no sweep, so a sweep has to be made out of what it has. Task-73 asked for the
two candidates to be measured before one was built, and this is the measuring, kept so it can
be run again: on a duct's cross-sections along a 90 degree bend and an S-bend, each route is
built by the modeller the app ships, inside Pyodide on :mod:`tools.stack`, and set against
the volume the sweep really has.

* **hulls** - a hull round each pair of neighbouring profile slices, the lot unioned. A
  profile with a hole is a second chain taken out of the first (run a millimetre past each
  end, so the cut is through rather than flush).
* **mesh** - :class:`bench.topology.Swept`: rings of the profile at the same stations, joined
  and capped in Python (:func:`bench.meshing.swept`) and handed over once as an import.

Both stand the profile at the same stations (:func:`bench.topology.sweep_stations`) and cut
its curves by the same chord rule, so what differs is only the route. The true volume is
Pappus's: the profile's area times the length of the path its centroid runs. Time is the
median of :data:`REPEATS` calls to the kernel's ``mesh``, which is what a run asks for.

Nothing is asserted: it prints a table, and the conclusion drawn from it is written down in
:mod:`bench.sweep`'s docstring and task-73's notes.
"""

import sys
from typing import Any

from tools import stack

REPEATS = 5
"""Timed builds per route and case; the median is the number worth reading."""

PROGRAM = """\
import json
import math
import statistics
import time

from pyodide.ffi import JsException

from bench import (
    ORIGIN,
    Bend,
    Point,
    Straight,
    Vector,
    X,
    centroid,
    circle,
    cut,
    face,
    fill,
    hull,
    path,
    polygon,
    rounded_rect,
    sweep,
    union,
)
from bench.adapters.browser import JsKernel
from bench.geometry import translation
from bench.topology import Arc, Face, Swept, Wire, moved, sweep_stations

Z = Vector(0.0, 0.0, 1.0)

PROFILES = {
    "rounded rect 40x30 r5": fill(rounded_rect(40, 30, 5, Point(-20, -15))),
    "circle d40": fill(circle(20)),
    "pipe d40 wall 3": face(circle(20), holes=(circle(17),)),
    "L 30x30 leg 10": fill(
        polygon(
            (
                Point(-15, -15),
                Point(15, -15),
                Point(15, -5),
                Point(-5, -5),
                Point(-5, 15),
                Point(-15, 15),
            )
        )
    ),
}

PATHS = {
    "90 bend r60": path(ORIGIN, Z, Straight(20), Bend(60, math.pi / 2, X), Straight(20)),
    "S-bend r60": path(
        ORIGIN, Z, Straight(10), Bend(60, math.pi / 4, X), Bend(60, math.pi / 4, -X), Straight(10)
    ),
}

TRUE_AREAS = {
    "rounded rect 40x30 r5": 40 * 30 - (4 - math.pi) * 25,
    "circle d40": math.pi * 400,
    "pipe d40 wall 3": math.pi * (400 - 289),
    "L 30x30 leg 10": 30 * 10 + 10 * 20,
}


def pappus(profile, along):
    # The length of the path the profile's centroid runs: a line's own length, and an arc's
    # turn times how far the centroid stands from its axis where the bend starts.
    middle = centroid(profile)
    run = 0.0
    edges = along.edges
    for i, e in enumerate(edges):
        c = e.curve
        if isinstance(c, Arc):
            here = sweep_stations(Swept(profile, Wire(edges[:i])))[-1] if i else None
            at = middle if here is None else here @ middle
            v = at - c.centre
            v = v - c.plane.normal * (v @ c.plane.normal)
            run += abs(c.end_angle - c.start_angle) * math.sqrt(v @ v)
        else:
            d = c.end - c.start
            run += math.sqrt(d @ d)
    return run


def chain(profile, stations):
    # A hull round each neighbouring pair of slices, unioned pairwise so no union is lopsided.
    slices = [moved(profile, t) for t in stations]
    pieces = [hull(a, b) for a, b in zip(slices, slices[1:])]
    while len(pieces) > 1:
        pieces = [
            union(*pieces[k : k + 2]) if k + 1 < len(pieces) else pieces[k]
            for k in range(0, len(pieces), 2)
        ]
    return pieces[0]


def hulls(profile, along):
    stations = list(sweep_stations(Swept(profile, along)))
    outer = Face(profile.plane, profile.outer)
    body = chain(outer, stations)
    if profile.inner:
        start_back = translation(profile.plane.normal * -1.0)
        end = stations[-1]
        end_on = end @ profile.plane.normal
        past = translation(end_on * 1.0) @ end
        inner = Face(profile.plane, profile.inner[0])
        body = cut(body, chain(inner, [start_back, *stations, past]), label="bore")
    return body


def euler(mesh):
    edges = set()
    for t in range(len(mesh.triangles) // 3):
        a, b, c = mesh.triangles[3 * t : 3 * t + 3]
        for p, q in ((a, b), (b, c), (c, a)):
            edges.add((min(p, q), max(p, q)))
    return len(mesh.vertices) // 3 - len(edges) + len(mesh.triangles) // 3


def measure(kernel, body, repeats):
    times = []
    for _ in range(repeats):
        began = time.perf_counter()
        mesh = kernel.mesh(body)
        times.append(time.perf_counter() - began)
    return {
        "volume": kernel.volume(body),
        "triangles": len(mesh.refs),
        "ms": 1000 * statistics.median(times),
        "euler": euler(mesh),
        "named": sorted({str(r) for r in mesh.refs if r is not None}),
    }


def main(js, given):
    repeats = json.loads(given)["repeats"]
    kernel = JsKernel(js, JsException)
    rows = []
    for route_name, along in PATHS.items():
        for profile_name, profile in PROFILES.items():
            exact = TRUE_AREAS[profile_name] * pappus(profile, along)
            for how, build in (("hulls", hulls), ("mesh", lambda p, a: sweep(p, a, label="duct"))):
                found = measure(kernel, build(profile, along), repeats)
                case = {"path": route_name, "profile": profile_name, "route": how}
                rows.append({**case, "exact": exact, **found})
    return json.dumps(rows)
"""


def _table(rows: list[dict[str, Any]]) -> str:
    """The rows as a fixed-width table, one line per route and case."""
    head = (
        f"{'path':<12} {'profile':<22} {'route':<6} {'volume':>10} {'error':>9} "
        f"{'tris':>6} {'ms':>8} {'V-E+F':>5} faces"
    )
    lines = [head, "-" * len(head)]
    for r in rows:
        error = (r["volume"] - r["exact"]) / r["exact"]
        faces = f"{len(r['named'])}: {', '.join(r['named'][:4])}" if r["named"] else "0"
        lines.append(
            f"{r['path']:<12} {r['profile']:<22} {r['route']:<6} {r['volume']:>10.1f} "
            f"{error:>+9.4%} {r['triangles']:>6} {r['ms']:>8.1f} {r['euler']:>5} {faces}"
        )
    return "\n".join(lines)


def main() -> int:
    """Build both routes for every case in the shipped stack and print what they measured."""
    reason = stack.missing()
    if reason is not None:
        print(f"cannot run: {reason}", file=sys.stderr)
        return 1
    rows: list[dict[str, Any]] = stack.run(PROGRAM, {"repeats": REPEATS})
    print(_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
