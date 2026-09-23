"""Where the host keeps its projects: one root, named by ``BENCH_PROJECTS``.

decision-9 puts a project on the host as a directory under a root the host designates, and
the app reaches it over the route ``web/server/projects.ts`` serves. That file resolves the
root for the app; this one resolves it for the command line, by the same rule, so the two can
never disagree about where a project is:

* ``BENCH_PROJECTS`` unset or empty is :data:`DEFAULT`, ``projects/`` at the top of the
  repository (gitignored).
* Set, it must be an absolute path. A relative one is refused rather than resolved, because
  Vite runs from ``web/`` and this from wherever it is started, and the two would resolve it
  against different directories.

A tool rather than a module of the package: it reads the environment, and nothing under
``src/bench`` knows a project is a directory.
"""

import os
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
"""The repository root."""

VARIABLE = "BENCH_PROJECTS"
"""The one environment variable that says where the projects are."""

DEFAULT = ROOT / "projects"
"""Where they are when nobody says."""


def projects_root(environ: Mapping[str, str] | None = None) -> Path:
    """The projects root ``environ`` designates - :data:`os.environ` when it is not given.

    Raises:
        ValueError: if the variable holds a relative path.
    """
    said = (os.environ if environ is None else environ).get(VARIABLE, "")
    if said == "":
        return DEFAULT
    path = Path(said)
    if not path.is_absolute():
        msg = f'{VARIABLE} must be an absolute path, and is "{said}"'
        raise ValueError(msg)
    return path


def _plain(name: str) -> bool:
    """Whether ``name`` is one plain name, as the route takes it: not empty, not ``.`` or
    ``..``, no path separator, no control character and not hidden."""
    return (
        name not in {"", ".", ".."}
        and "/" not in name
        and "\\" not in name
        and not name.startswith(".")
        and all(ord(c) >= 0x20 and c != "\x7f" for c in name)
    )


def project_file(project: str, file: str, environ: Mapping[str, str] | None = None) -> Path:
    """The file called ``file`` in the project called ``project``, under the root - both one
    plain name each, the same rule the route keeps, so the command line reaches exactly what
    the app can and nothing beside it.

    Raises:
        ValueError: if either is not one plain name, or the root is refused.
    """
    for name in (project, file):
        if not _plain(name):
            msg = f"{name!r} is not a plain name"
            raise ValueError(msg)
    return projects_root(environ) / project / file
