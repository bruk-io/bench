"""Shadow: which of a project's own file names would silently replace something a script
already trusts.

A project (decision-9) can be more than one script: its entry imports a module beside it -
``tools/build.py`` puts the project directory on the import path, and
``web/src/worker.py``'s ``bench.worker.start`` mounts the same files into the browser's
runtime. Either way, a project file named ``os.py`` or ``bench.py`` would resolve before the
real one whenever it happens to come first on ``sys.path`` - not an error, just the wrong
module, which is worse. :func:`shadowed` is the one place that rule is written, so the command
line and the browser can never disagree about which names are refused.

**Third-party names (task-56).** The same risk exists for anything else importable in the
runtime a project file happens to be named after, not only the standard library. Checked
against the actual runtime rather than guessed: ``web/src/worker.ts`` calls no
``pyodide.loadPackage`` and ``pyproject.toml`` declares no ``dependencies``, so nothing
third-party is shipped for a script to reach at all - ``manifold-3d`` is Manifold's own npm
package, driven from JavaScript (``web/src/modeller.ts``), never imported as Python. What *is*
there without being loaded is Pyodide's own runtime, ``js`` and ``pyodide`` themselves,
importable the moment a script runs in the browser the same way ``os`` always is - so those two
join the reserved set for the reason ``os`` is in it, and no others are reserved on the
strength of a name that might be loaded one day. A package added later the same way would need
adding here too, the day it is.
"""

import sys
from collections.abc import Iterable

_RESERVED = frozenset(sys.stdlib_module_names) | {"bench", "js", "pyodide"}
"""Every name a project file must not be called: the standard library's own module names,
``bench`` itself, and the two Pyodide gives every script in the browser without loading
anything - ``js`` and ``pyodide``. Not ``numpy`` or ``manifold3d``: neither is actually
importable in this runtime today (see the module docstring)."""


def shadowed(names: Iterable[str]) -> str | None:
    """The first of ``names`` - a project's ``.py`` file names - that would shadow the
    standard library or ``bench``, or ``None`` if none would.

    ``names`` are file names, not module names: ``"parts.py"`` is passed whole, and only the
    stem before ``.py`` is checked, since that is the name Python binds on import. A name with
    no ``.py`` suffix is checked as it is, so a caller that already has stems can pass those
    too.
    """
    for name in names:
        stem = name[:-3] if name.endswith(".py") else name
        if stem in _RESERVED:
            return name
    return None
