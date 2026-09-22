"""The one command that gates a change: ``uv run tools/check.py``.

Runs, in order, stopping at the first failure: ``ruff check``, ``ruff format --check``,
``mypy``, the web app's ``tsc``, its component lint (ESLint's Lit and custom-element rules,
and ``lit-analyzer`` over the templates) and its component tests, the default pytest suite twice in
this same process, and finally the ``e2e`` layer. ``--fast`` (or ``--no-e2e``, its plainer
spelling) skips that last layer, since it drives a real browser and is slow. The two web
steps say they were skipped, rather than failing, when ``web/node_modules`` is absent - the
same condition the browser and ``e2e`` layers skip on.

Between the two pytest runs, ``bench`` and every ``bench.*`` module is popped out of
``sys.modules``, along with every test module that already imported names out of them - see
:func:`_reset_bench_modules` - so the second run imports the package from scratch rather than
reusing the first run's module objects. That catches two different kinds of leftover state in
one pass: a dirty global the first run left behind (a mutable default, a cache a function
filled in), which a plain re-run over the same modules would already have caught, and
anything a module does once at import time - a computed constant, a registration - which
only a fresh import exercises again.

Running pytest twice via :func:`pytest.main` in one process is supported by pytest itself;
verified here to raise no plugin- or fixture-registration warnings, and Playwright's sync API
(used by the ``e2e`` layer) is verified to still work in-process afterwards - so everything
below runs in-process, with no subprocess pytest at all.

Raises:
    SystemExit: with a non-zero code, from the first failing step.
"""

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

_TARGETS = ("src", "tests", "tools")
_ROOT = Path(__file__).resolve().parent.parent
_TESTS = _ROOT / "tests"
_WEB = _ROOT / "web"


def _banner(title: str) -> None:
    print(f"\n{'=' * 10} {title} {'=' * 10}", flush=True)


def _run_subprocess(title: str, argv: tuple[str, ...]) -> bool:
    _banner(title)
    return subprocess.run(argv, check=False).returncode == 0


def _run_web(title: str, script: str) -> bool:
    """Run one of ``web/package.json``'s scripts, or say it was skipped when there are no
    ``node_modules`` to run it with."""
    if not (_WEB / "node_modules").is_dir():
        _banner(f"{title} - SKIPPED: web/node_modules missing, run npm install in web/")
        return True
    return _run_subprocess(title, ("npm", "--prefix", str(_WEB), "run", script))


def _run_pytest(title: str, argv: list[str]) -> bool:
    """Run one in-process pytest. ``argv`` is a ``list`` because :func:`pytest.main` takes
    one, not any sequence; every other argument list here is a tuple."""
    _banner(title)
    return pytest.main(argv) == 0


def _is_bench(name: str) -> bool:
    return name == "bench" or name.startswith("bench.")


def _is_test_module(name: str, module: object) -> bool:
    """Whether ``module`` was imported from under ``tests/`` - however pytest happened to
    name it, since a directory with no ``__init__.py`` is imported by its bare filename
    (``test_ops``), not a dotted path (``tests.unit.test_ops``)."""
    path = getattr(module, "__file__", None)
    if path is None:
        # A directory with no ``__init__.py`` imported by its dotted name is a namespace
        # package with no file of its own - and it still holds every submodule as an
        # attribute, so ``from tests.adapter import cases`` would hand back the first run's.
        return name == "tests" or name.startswith("tests.")
    try:
        Path(path).resolve().relative_to(_TESTS)
    except ValueError:
        return name == "tests" or name.startswith("tests.")
    return True


def _reset_bench_modules() -> bool:
    """Drop ``bench`` and every ``bench.*`` module from ``sys.modules``, and every test
    module that already imported names out of them.

    The next ``import bench`` (or anything under it) then runs the package's module bodies
    again from source, instead of handing back the objects the first pytest run already
    made. A test module bound to those old objects at collection time - ``from bench import
    Part``, ``from bench.library import gridfinity`` - is dropped along with them, or an
    ``isinstance`` or ``match`` in a test would compare the second run's fresh instances
    against the first run's classes and fail for a reason that has nothing to do with
    ``bench``: pytest does not re-import a test module it already has cached, so nothing
    else makes it rebind those names to the second run's fresh module. Always succeeds:
    this is a reset between steps, not a check of its own.
    """
    _banner("resetting bench's and tests' modules before the second run")
    for name, module in list(sys.modules.items()):
        if _is_bench(name) or _is_test_module(name, module):
            del sys.modules[name]
    return True


def main(argv: Sequence[str] | None = None) -> int:
    """Run every check in order, stopping at the first failure.

    Returns:
        ``0`` if every step passed, ``1`` at the first step that failed.
    """
    args = sys.argv[1:] if argv is None else argv
    skip_e2e = "--fast" in args or "--no-e2e" in args

    steps: list[Callable[[], bool]] = [
        lambda: _run_subprocess("ruff check", (sys.executable, "-m", "ruff", "check", *_TARGETS)),
        lambda: _run_subprocess(
            "ruff format --check", (sys.executable, "-m", "ruff", "format", "--check", *_TARGETS)
        ),
        lambda: _run_subprocess("mypy", (sys.executable, "-m", "mypy")),
        lambda: _run_web("tsc (web)", "typecheck"),
        lambda: _run_web("eslint + lit-analyzer (web)", "lint"),
        lambda: _run_web("component tests (web)", "test"),
        lambda: _run_pytest("pytest (run 1 of 2)", ["-q"]),
        _reset_bench_modules,
        lambda: _run_pytest("pytest (run 2 of 2 - bench re-imported from scratch)", ["-q"]),
    ]
    if not skip_e2e:
        steps.append(lambda: _run_pytest("pytest -m e2e", ["-q", "-m", "e2e"]))

    for step in steps:
        if not step():
            _banner("FAILED")
            return 1
    _banner("ALL CHECKS PASSED" + (" (e2e skipped)" if skip_e2e else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
