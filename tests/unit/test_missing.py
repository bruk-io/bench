"""Unit: :mod:`bench.missing` alone - what a ``ModuleNotFoundError`` means for a project,
in its own terms. See the module docstring for the three cases it tells apart.
"""

import pytest

from bench.missing import explained

pytestmark = pytest.mark.unit


def test_a_missing_top_level_name_names_the_file_and_lists_the_project() -> None:
    assert explained("sidekick", ["parts", "gizmo"]) == (
        "if sidekick was meant to be a project file, there is no sidekick.py (it has: gizmo.py,"
        " parts.py); if it was meant to be a package, this runtime does not provide sidekick"
        " either"
    )


def test_a_project_with_no_other_files_says_so_rather_than_an_empty_list() -> None:
    assert explained("sidekick", []) == (
        "if sidekick was meant to be a project file, there is no sidekick.py (it has none); if"
        " it was meant to be a package, this runtime does not provide sidekick either"
    )


def test_a_third_party_name_is_not_called_a_missing_project_file() -> None:
    """AC#2: `requests` gets the same either/or as `sidekick` - naming what the project has,
    never asserting the missing name was meant to be one of its own files."""
    message = explained("requests", ["parts"])
    assert message is not None
    assert "there is no requests.py" in message
    assert "this runtime does not provide requests either" in message


def test_a_dotted_name_is_a_submodule_of_a_real_package_not_a_project_file() -> None:
    """`import bench.nope`: `bench` exists, so this is not a project file question at all -
    ``None`` leaves Python's own message alone."""
    assert explained("bench.nope", ["parts"]) is None


def test_no_name_at_all_says_nothing_either() -> None:
    assert explained(None, ["parts"]) is None


def test_a_name_the_project_could_never_have_written_is_not_called_a_missing_file() -> None:
    """AC#3: a stdlib name (or `bench`, `js`, `pyodide`) is refused as a project file by
    :func:`bench.shadow.shadowed`, so a `ModuleNotFoundError` for one - including a stdlib
    piece this runtime's Pyodide build unvendors, like `_sqlite3` - never suggests writing a
    file that could not exist."""
    message = explained("_sqlite3", [])
    assert message is not None
    assert "cannot have a file named _sqlite3.py" in message
    assert "does not provide _sqlite3" in message
    assert ".py (it has" not in message, "never phrased as a missing project file"


@pytest.mark.parametrize("name", ["os", "bench", "js", "pyodide"])
def test_every_reserved_name_gets_the_same_treatment(name: str) -> None:
    message = explained(name, [])
    assert message is not None
    assert f"cannot have a file named {name}.py" in message
