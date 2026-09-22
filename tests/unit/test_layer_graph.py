"""The layer graph in ``pyproject.toml`` matches what ``src/bench`` actually imports.

Mirrors, in plain :mod:`ast`, the `pypeeker` `import-boundaries` rule the project is not
guaranteed to have installed: every bench-to-bench import in ``src/bench`` must appear in its
module's allow-list under ``[tool.pypeeker.import-boundaries]``, and every module on disk
(barrels aside) must be declared there at all - a new module cannot join the tree without
choosing its layer. Imports inside an ``if TYPE_CHECKING:`` block are annotations, not runtime
dependencies, so they are collected separately and not checked against the allow-list.

Beside it, the one rule the table cannot express, because it is about the outside world
rather than about bench: **no module under ``src/bench`` imports a solid modeller, or anything
that only exists inside Pyodide.** ``kernel.py`` defines the seam - a Protocol and a record -
and the kernel in ``adapters/`` is handed the modeller it drives, and the exception a refusal
raises, by its host. So ``import bench`` needs nothing installed and runs, and is tested, in
any Python.
"""

import ast
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src" / "bench"


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _type_checking_ids(tree: ast.Module) -> set[int]:
    """Identities of every import node that lives inside an ``if TYPE_CHECKING:`` body."""
    return {
        id(imp)
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and _is_type_checking(node.test)
        for imp in ast.walk(node)
        if isinstance(imp, ast.Import | ast.ImportFrom)
    }


def _resolve(package: str, level: int, module: str | None) -> str:
    """The absolute dotted name a (possibly relative) import target names."""
    if level == 0:
        return module or ""
    base = package.rsplit(".", level - 1)[0]
    return f"{base}.{module}" if module else base


def _bench_targets(tree: ast.Module, package: str, skip: set[int], known: set[str]) -> set[str]:
    """Bench modules ``tree`` imports at runtime, as dotted names relative to ``bench``.

    ``from bench.library import gridfinity`` names a submodule as an imported symbol, so a
    ``from X import a, b`` whose alias is itself a known module (``X.a`` in ``known``) targets
    that submodule rather than ``X`` - the only way a package import (``library``) can resolve
    to the one real module beneath it (``library.gridfinity``).
    """
    targets: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("bench."):
                    targets.add(alias.name.removeprefix("bench."))
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve(package, node.level, node.module)
            if not resolved.startswith("bench."):
                continue
            rel = resolved.removeprefix("bench.")
            submodules = {f"{rel}.{a.name}" for a in node.names if f"{rel}.{a.name}" in known}
            targets |= submodules or {rel}
    return targets


def _modules() -> dict[str, Path]:
    """Every non-barrel module under ``src/bench``, keyed by its dotted name relative to it."""
    found: dict[str, Path] = {}
    for path in _SRC.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        parts = path.relative_to(_SRC).with_suffix("").parts
        found[".".join(parts)] = path
    return found


def _boundaries() -> dict[str, list[str]]:
    """The allow-table from ``pyproject.toml``, typed: :mod:`tomllib` hands back ``Any``,
    and an ``Any`` here would let the rest of this test mean anything."""
    table: dict[str, list[str]] = tomllib.loads((_ROOT / "pyproject.toml").read_text())["tool"][
        "pypeeker"
    ]["import-boundaries"]
    return table


def test_every_import_stays_within_its_layer() -> None:
    boundaries = _boundaries()
    modules = _modules()
    assert set(modules) <= set(boundaries), (
        f"undeclared modules: {sorted(set(modules) - set(boundaries))} - "
        "add them to [tool.pypeeker.import-boundaries] in pyproject.toml"
    )

    known = set(modules)
    problems: list[str] = []
    for name, path in modules.items():
        package = "bench" if "." not in name else "bench." + name.rsplit(".", 1)[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        allowed = set(boundaries[name])
        for target in _bench_targets(tree, package, _type_checking_ids(tree), known):
            if target not in allowed:
                problems.append(
                    f"{name} imports {target!r}, which is not in its allowed list {sorted(allowed)}"
                )
    assert not problems, "layer graph violated:\n" + "\n".join(sorted(problems))


def test_every_declared_module_is_on_disk() -> None:
    """A row for a module that has gone is a layer nobody can check against."""
    gone = set(_boundaries()) - set(_modules())
    assert not gone, f"pyproject.toml declares modules that do not exist: {sorted(gone)}"


_OUTSIDE = frozenset({"manifold3d", "pyodide", "js", "numpy"})
"""What ``src/bench`` never imports: a solid modeller, and the modules that exist only inside
Pyodide. The kernel is handed its modeller, and the exception a refusal raises, at the edge."""


def _foreign_imports(tree: ast.Module) -> set[str]:
    """Every top-level package this module imports that is not ``bench`` itself."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {alias.name.partition(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.partition(".")[0])
    return out


def test_nothing_in_the_package_imports_a_modeller_or_the_browser() -> None:
    """The rule the pypeeker table cannot state, for every module, ``adapters/`` included:
    ``import bench`` needs nothing installed and nothing only a browser has."""
    problems: list[str] = []
    for name, path in sorted(_modules().items()):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for found in sorted(_foreign_imports(tree) & _OUTSIDE):
            problems.append(f"{name} imports {found!r}")
    assert not problems, "the package reached outside itself:\n" + "\n".join(problems)


def test_the_kernel_module_is_the_seam_and_nothing_behind_it() -> None:
    """``kernel.py`` names the Protocol and the transport record; it imports no adapter, so
    importing it costs nothing and drags nothing in."""
    path = _modules()["kernel"]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not _bench_targets(tree, "bench", set(), set(_modules())) & {
        name for name in _modules() if name.startswith("adapters.")
    }
