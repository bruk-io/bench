"""Session-wide guards for the test suite's layers.

Two things happen here, both mechanical and both in service of the "no doubles" rule the
layer split exists to enforce:

* :func:`pytest_collection_finish` reads every ``*.py`` under ``tests/`` - not only
  ``test_*`` files and ``conftest.py``, so a shared helper module like ``tests/support.py``
  is read too - with :mod:`ast` and fails the session outright if one imports ``unittest``
  in any form (bare, ``unittest.mock``, the standalone ``mock`` backport, or a
  ``from unittest import ...``), or if any function in it takes a ``monkeypatch`` or
  ``mocker`` argument - what a test reaches for when it wants a double. A plain text search
  over the same files also flags two things an import or an argument name would not show:
  building pytest's fixture-granting class directly instead of asking for it as a fixture,
  and reaching for the standard library's dynamic module loader, which can load a real
  module as an unchecked stand-in with no ``import`` statement at all. All four layers are
  guarded, not only the pure two: a double belongs at the world boundary and only as a fake
  that asserts on state, and neither a mocking library nor a patched-away attribute is one.
  A hand-written fake is a class, so the guard does not stand in its way. The files are read
  off disk rather than from the collected items, so deselecting a layer (the default
  ``-m 'not e2e'``) cannot carry it out of reach, and a fixture hiding in a ``conftest.py``
  is read along with the tests.

  This is a tripwire, not a proof: it is a mechanical scan for the names a double is built
  from, always worth running because it is nearly free, but it cannot see a double built to
  dodge every name here, and it says nothing about whether a hand-written fake actually
  behaves like the real boundary it stands in for. It catches the easy, common ways in, not
  every way in.
* :func:`pytest_collection_modifyitems` is the safety net: it marks every item ``unit``,
  ``functional``, ``adapter`` or ``e2e`` from its path under ``tests/`` when the item does
  not already carry that marker, so a file that forgets ``pytestmark`` still lands in the
  right layer.
"""

import ast
from pathlib import Path

import pytest

_BANNED_MODULES = frozenset({"mock", "unittest", "unittest.mock"})
_BANNED_ARGS = frozenset({"monkeypatch", "mocker"})
# Built from parts, not written whole: each is the exact text this file's own docstrings
# describe, and a literal copy here would trip this very guard on this very file.
_BANNED_TEXT = ("Monkey" + "Patch(", "importlib" + ".import_module(")
_LAYERS = ("unit", "functional", "adapter", "e2e")


def _banned_import(tree: ast.Module) -> str | None:
    """The first banned import in ``tree``, described as the statement itself, if any.

    ``unittest`` is banned whole, not only its ``mock`` submodule: nothing in this project
    needs any of it, and a name banned only halfway is a gap the next test finds.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _BANNED_MODULES or alias.name.startswith("unittest."):
                    return f"import {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in _BANNED_MODULES or module.startswith("unittest."):
                names = ", ".join(alias.name for alias in node.names)
                return f"from {module} import {names}"
    return None


def _banned_argument(tree: ast.Module) -> str | None:
    """The first function taking a banned argument, described as ``name(arg)``.

    Every function counts, not only ``test_*``: a fixture or a helper that asks for
    ``monkeypatch`` is asking for it on some test's behalf.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = node.args
            names = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
            for banned in sorted(_BANNED_ARGS):
                if banned in names:
                    return f"{node.name}({banned})"
    return None


def _banned_text(source: str) -> str | None:
    """The first of :data:`_BANNED_TEXT` that appears anywhere in ``source``, verbatim.

    A plain substring search rather than another :mod:`ast` walk: constructing pytest's
    monkeypatch fixture class directly needs no ``monkeypatch`` argument for the argument
    check above to see, and the standard library's dynamic import function can load a real
    module as a stand-in with no ``import`` statement for the import check to see either.
    Textual is cheaper to write and over-inclusive in the same direction the rest of this
    guard already is - a tripwire, not a proof.
    """
    for needle in _BANNED_TEXT:
        if needle in source:
            return needle
    return None


def _guarded_files(tests_dir: Path) -> tuple[Path, ...]:
    """Every ``*.py`` under ``tests/``, whatever this run selected - not only ``test_*``
    files and ``conftest.py``, so a helper module more than one test file imports (like
    ``tests/support.py``) is read along with them."""
    return tuple(sorted(tests_dir.rglob("*.py")))


def _layer_of(path: Path, tests_dir: Path) -> str | None:
    """The top-level directory under ``tests/`` that ``path`` lives in, or ``None``."""
    try:
        parts = path.relative_to(tests_dir).parts
    except ValueError:
        return None
    return parts[0] if parts else None


def pytest_collection_finish(session: pytest.Session) -> None:
    """Fail the session (via :func:`pytest.exit`) if any file under ``tests/`` reaches for
    a double: an import of ``unittest`` in any form, a function taking a ``monkeypatch`` or
    ``mocker`` argument, or either text pattern in :data:`_BANNED_TEXT`."""
    tests_dir = Path(str(session.config.rootpath)) / "tests"
    problems: list[str] = []
    for path in _guarded_files(tests_dir):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        bad_import = _banned_import(tree)
        if bad_import is not None:
            problems.append(f"{path}: {bad_import}")
        bad_argument = _banned_argument(tree)
        if bad_argument is not None:
            problems.append(f"{path}: {bad_argument}")
        bad_text = _banned_text(source)
        if bad_text is not None:
            problems.append(f"{path}: uses {bad_text!r}")
    if problems:
        detail = "\n".join(f"  {problem}" for problem in problems)
        pytest.exit(f"no doubles anywhere in tests:\n{detail}", returncode=1)


def pytest_collection_modifyitems(session: pytest.Session, items: list[pytest.Item]) -> None:
    """Add the layer marker a path implies to any item that did not already carry one."""
    tests_dir = Path(str(session.config.rootpath)) / "tests"
    for item in items:
        layer = _layer_of(item.path, tests_dir)
        if layer in _LAYERS and layer not in {mark.name for mark in item.iter_markers()}:
            item.add_marker(getattr(pytest.mark, layer))
