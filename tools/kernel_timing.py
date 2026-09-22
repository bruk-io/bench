"""Time a run with its kernel: ``uv run python -m tools.kernel_timing [example.py ...]``.

A look at how long the app takes to run a printed example, not a check of whether it is
right - so nothing here fails and nothing is asserted. Every example named (or every one in
:data:`PRINTED` when none are) is run the way the worker runs it, inside Pyodide with the
app's modeller as its kernel, on :mod:`tools.stack`.

The measuring is the standard library's, run inside the same interpreter as the work:
:func:`timeit.repeat` for how long a whole :func:`bench.script.run` takes, after one warm-up
run, and one more run under :mod:`profiling.tracing` read back with :mod:`pstats` for how
much of it went on the kernel's three calls. The profiled run is slower than the timed ones,
so its answer is given as a share of that run rather than as milliseconds.
"""

import statistics
import sys
from typing import Any

from tools import stack

EXAMPLES = stack.ROOT / "examples"

PRINTED = (
    "gridfinity_bin.py",
    "hinge.py",
    "depth_stop_collar.py",
    "pipe_bracket.py",
    "enclosure_lid.py",
)
"""What is timed when the caller names nothing: every example with a printed body."""

REPEATS = 7
"""Timed runs per example after the warm-up; the median is the number worth reading."""

PROGRAM = """\
import json
import pstats
import timeit
from profiling.tracing import Profile

from pyodide.ffi import JsException

from bench import script
from bench.adapters.browser import JsKernel

KERNEL_CALLS = frozenset({"mesh", "volume", "min_gap"})


def main(js, given):
    given = json.loads(given)
    kernel = JsKernel(js, JsException)
    out = {}
    for name, source in given["sources"].items():
        def once(source=source):
            return script.run(source, kernel=kernel)

        scene = once()
        if not scene["ok"]:
            raise RuntimeError(f"{name}: {scene['error']['message']}")
        times = timeit.repeat(once, number=1, repeat=given["repeats"])
        profile = Profile()
        profile.runcall(once)
        stats = pstats.Stats(profile)
        in_kernel = sum(
            cumulative
            for (file, _, function), (_, _, _, cumulative, _) in stats.stats.items()
            if file.endswith("adapters/browser.py") and function in KERNEL_CALLS
        )
        out[name] = {
            "times": times,
            "kernel_share": in_kernel / stats.total_tt if stats.total_tt else 0.0,
            "triangles": sum(
                len(part["mesh"]["ref_index"]) for part in scene["parts"] if part["mesh"]
            ),
        }
    return json.dumps(out)
"""


def _table(timed: dict[str, Any]) -> str:
    """The timings as a person reads them: example, triangles, fastest and median run, and
    the kernel's share of a run."""
    width = max(len(name) for name in timed)
    lines = [f"{'example':<{width}}  {'triangles':>9}  {'min ms':>8}  {'median ms':>9}  kernel"]
    total = 0.0
    for name, one in timed.items():
        times = [1000 * seconds for seconds in one["times"]]
        median = statistics.median(times)
        total += median
        lines.append(
            f"{name:<{width}}  {one['triangles']:>9}  {min(times):>8.1f}  {median:>9.1f}"
            f"  {100 * one['kernel_share']:>5.0f}%"
        )
    lines.append(f"{'total of medians':<{width}}  {'':>9}  {'':>8}  {total:>9.1f}")
    return "\n".join(lines)


def main(argv: tuple[str, ...] | None = None) -> int:
    """Run every named example with its kernel and print how long each run took.

    Returns:
        ``0``, always - a timing has no verdict to give.
    """
    named = tuple(sys.argv[1:] if argv is None else argv)
    names = tuple(one if one.endswith(".py") else f"{one}.py" for one in named) or PRINTED
    given = {
        "sources": {name.removesuffix(".py"): (EXAMPLES / name).read_text() for name in names},
        "repeats": REPEATS,
    }
    print(_table(stack.run(PROGRAM, given)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
