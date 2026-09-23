"""Missing: an import that failed, in a project's own terms rather than Python's.

A script (task-50) can be more than one file, and an entry that says ``import sidekick``
either reaches a ``sidekick.py`` a maker wrote beside it, or fails with Python's own
``ModuleNotFoundError: No module named 'sidekick'`` - true, but silent about the one thing a
maker actually wants to know: what the project has instead. :func:`bench.script.run` is the
one place both the worker (``src/bench/worker.py``, the project's other scripts mounted for
each run) and ``tools/build.py`` (the project directory on the import path) route a run
through, so :func:`explained` is the one place their shared knowledge - what a project's own
files are called - turns Python's message into one that says so, the way
:func:`bench.shadow.shadowed` keeps the shadowing rule in one place.

**Three branches, not two (task-56).** A missing name is one of:

1. Dotted, ``"bench.nope"`` for ``import bench.nope`` - a submodule of a package that does
   exist. A project's own modules are never named at more than one level, so this says
   nothing about one and gives back ``None``, leaving Python's own message alone.
2. A name :func:`bench.shadow.shadowed` would refuse a project file for - the standard
   library, ``bench``, or Pyodide's own ``js``/``pyodide`` (which includes stdlib pieces the
   runtime unvendors, such as ``_sqlite3``: real names, real ``ModuleNotFoundError``\\ s,
   just never a project's own file). The project *cannot* have written this one, so this says
   only that the runtime does not provide it - never that a file is missing.
3. A plain top-level name that is neither: it might be a project file the maker has not
   written, or a third-party package this runtime does not provide - nothing here can tell
   the two apart, so it says both rather than guess which was meant.
"""

from collections.abc import Iterable

from .shadow import shadowed


def explained(missing: str | None, modules: Iterable[str]) -> str | None:
    """What a :class:`ModuleNotFoundError` named ``missing`` - its own ``.name`` - means for a
    project whose other files are ``modules``, as their stems, the same shape
    :func:`bench.shadow.shadowed` takes a project's file names in; or ``None`` when nothing
    more honest can be said than Python's own message. See the module docstring for the three
    cases this tells apart.
    """
    if missing is None or "." in missing:
        return None
    if shadowed([missing]) is not None:
        return (
            f"the project cannot have a file named {missing}.py - it would shadow the"
            f" standard library or the runtime itself - and this runtime does not provide"
            f" {missing} either"
        )
    names = sorted(modules)
    has = f"it has: {', '.join(f'{name}.py' for name in names)}" if names else "it has none"
    return (
        f"if {missing} was meant to be a project file, there is no {missing}.py ({has}); if it"
        f" was meant to be a package, this runtime does not provide {missing} either"
    )
