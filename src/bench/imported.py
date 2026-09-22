"""A mesh somebody else made, as a body this package can build with.

One verb. :func:`imported` wraps the :class:`~bench.kernel.Mesh` a host dropped on the view -
``reference`` in a script's own namespace - as a :class:`~bench.topology.Solid`, and from
there it is a solid like any other: ``union``, ``cut``, ``common``, ``hull``,
``kernel.volume``, ``kernel.min_gap``, ``check_clearance``, ``check_contact``. That is the
whole point of it, and the reason a candidate can finally be *boolean* compared against a
real object rather than only survey-diffed against one: how much of a candidate's volume
lies inside the reference is ``kernel.volume(common(candidate, imported(reference)))``.

A module of its own rather than a function in :mod:`bench.solids`, and the layer graph is
why: ``solids`` promises in its own docstring that no kernel is imported there, and the
``Mesh`` record this verb takes lives in :mod:`bench.kernel`. Putting it there would hand
the kernel seam to ``features`` and every library above it as well. So this sits beside
:mod:`bench.placement` and :mod:`bench.survey` - the other modules whose subject is a mesh
that already exists - and is the one place that knows both a ``Mesh`` and a ``Solid``.

Nothing here validates anything. Whether a mesh is a body at all is the modeller's own
question, asked when something actually builds it, and answered the way every other refusal
in this package is: a :class:`ValueError` naming the call.
"""

from .kernel import Mesh
from .topology import Imported, Label, Solid
from .topology import label as _label


def imported(mesh: Mesh, *, label: str | Label | None = None) -> Solid:
    """``mesh`` as a body: a :class:`~bench.topology.Solid` wrapping its own triangles.

    The one argument is the mesh itself - a placed ``reference``, or anything
    :func:`bench.survey.mesh_from_stl` read - because there is nothing else to say about it.
    Where it sits is already settled by the time a script sees it (:mod:`bench.placement`
    applies the project's ``[reference]`` table at the host's edge), so this asks for no
    plane, no table and no way up; move it afterwards with :func:`bench.solids.move` like any
    other solid if a script wants it somewhere else. ``label`` is the keyword every other
    constructor here takes - ``cuboid``, ``cylinder``, ``hull`` - and naming the whole body is
    all it can do: an import has no faces of its own to name, the way a hull has none.

    The mesh's own ``refs`` are dropped, which is honest rather than lossy: a mesh read out
    of a file has none, and one meshed from a body carries names that belong to the body it
    came from and not to the triangles once a kernel has rebuilt them.

    A mesh the modeller will not take - an open boundary, a non-finite vertex - raises when
    something builds this solid, not here; a mesh wound inside-out is *accepted* by the
    modeller and measures a negative volume, which nothing here catches either.
    """
    return Solid(Imported(mesh.vertices, mesh.triangles), None if label is None else _label(label))
