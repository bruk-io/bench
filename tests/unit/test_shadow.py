"""Unit: :mod:`bench.shadow` alone - which project file names would shadow something the
runtime already gives a script.
"""

import pytest

from bench.shadow import shadowed

pytestmark = pytest.mark.unit


def test_a_stdlib_name_is_refused() -> None:
    assert shadowed(["os.py"]) == "os.py"


def test_bench_itself_is_refused() -> None:
    assert shadowed(["bench.py"]) == "bench.py"


def test_an_ordinary_project_name_is_not_refused() -> None:
    assert shadowed(["parts.py", "gizmo.py"]) is None


@pytest.mark.parametrize("name", ["js.py", "pyodide.py"])
def test_pyodides_own_names_are_refused_too(name: str) -> None:
    """task-56: the browser hands every script ``js`` and ``pyodide`` without loading
    anything, exactly the way it always has ``os`` - a project file called either would
    resolve first on ``sys.path`` and answer with the wrong thing, silently, the same risk
    the standard library's own names already are."""
    assert shadowed([name]) == name


@pytest.mark.parametrize("name", ["numpy.py", "manifold3d.py"])
def test_names_of_packages_the_runtime_does_not_actually_ship_are_not_reserved(
    name: str,
) -> None:
    """The other half of the same decision: reserving a name on the strength of a package
    that might be loaded one day would refuse a maker's own file for nothing real to shadow.
    Checked against the runtime as it stands - ``web/src/worker.ts`` calls no
    ``pyodide.loadPackage`` and ``pyproject.toml`` has no ``dependencies`` - so neither
    ``numpy`` nor ``manifold3d`` (Manifold is driven from JavaScript, never imported as
    Python) is importable in this runtime at all, and nothing here pretends otherwise."""
    assert shadowed([name]) is None
