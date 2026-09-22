"""bench.library: objects worth shipping, each module one thing you can make.

``gridfinity`` is a laser-cut drawer cabinet sized in Gridfinity units and ``gridfinity3d``
the printed bin that goes in its drawers. ``print`` is the odd one out and the exception
that says the rule: not an object but the domain a printed object is made in - the filament
profiles, the fits and the build volumes - which lives here rather than in the core so that
the layer graph can say what may read it. The modules are exported rather than their names,
so two libraries can both have a ``Spec``."""

from . import gridfinity, gridfinity3d, print

__all__ = ["gridfinity", "gridfinity3d", "print"]
