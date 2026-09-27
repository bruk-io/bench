"""A host project for the tools that open one - :mod:`tools.build` and :mod:`tools.qa` - as
files written onto a projects root of a test's own, never the repository's ``projects/``.

Held as text and written on demand, the way ``tests/e2e/test_project_modules.py`` seeds its
own, rather than as ``.py`` files on disk under ``tests/``: a project's entry says ``from bench
import *`` and ``import sizes``, which the gate's ruff and mypy would read as this package's
own modules and refuse.

It is the smallest project that has everything a real one has and a tool has to get right:
a declared entry that is not named for the directory, a sibling module the entry imports, a
second script that is not the entry, and a printed body with a check only a kernel can answer
- a cap wider than the post it stands on, whose underside :func:`bench.check_overhangs` has to
measure. Without a modeller that check reads ``unchecked``; with one it reports.
"""

from pathlib import Path

NAME = "probe"
"""The project's directory name under the root."""

ENTRY = "stand.py"
"""The script ``[project] entry`` names - not ``probe.py``, so a tool that guessed the entry
from the directory's name would pick nothing."""

OTHER = "plate.py"
"""The project's other script: a cut part, with no body for a kernel to measure."""

FILES = {
    "bench.toml": f'[project]\nentry = "{ENTRY}"\n\n[values]\n',
    "sizes.py": "POST = 10.0\nCAP = 30.0\nTALL = 20.0\n",
    ENTRY: (
        "from bench import *\n"
        "from bench.library.print import PLA\n"
        "\n"
        "import sizes\n"
        "\n"
        "pla = Printed(PLA)\n"
        "post = cuboid(sizes.POST, sizes.POST, sizes.TALL, label='post')\n"
        "inset = (sizes.CAP - sizes.POST) / 2\n"
        "cap = move(cuboid(sizes.CAP, sizes.CAP, 4.0, label='cap'),"
        " Vector(-inset, -inset, sizes.TALL))\n"
        "stand = union(post, cap)\n"
        "check_overhangs(stand, pla.orient, PLA)\n"
        "show(part('stand', stand, pla))\n"
    ),
    OTHER: (
        "from bench import *\n"
        "\n"
        "import sizes\n"
        "\n"
        "show(part('plate', fill(rect(sizes.CAP, sizes.CAP)), Stock(3, 'ply')))\n"
    ),
}
"""Every file of the project, by name."""


def seeded(root: Path) -> Path:
    """The project written under ``root``, and its directory."""
    directory = root / NAME
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in FILES.items():
        (directory / name).write_text(text)
    return directory
