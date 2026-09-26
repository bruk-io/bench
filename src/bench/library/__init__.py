"""bench.library: objects worth shipping, each module one thing you can make.

``gridfinity`` is a laser-cut drawer cabinet sized in Gridfinity units and ``gridfinity3d``
the printed bin that goes in its drawers. ``ducts`` is the first standards library built on
the operations below it: a table of real hose and duct sizes, each citing where its number
comes from, and the printed fittings that join them - spigot, socket, coupler, reducer,
elbow, branch and square-to-round - turned, swept and hollowed with ``shell`` and ``sweep``.
``print`` is the odd one out and the exception that says the rule: not an object but the
domain a printed object is made in - the filament profiles, the fits and the build volumes -
which lives here rather than in the core so that the layer graph can say what may read it.

The library stays flat for now: one module per ecosystem, beside each other, and no
``parts/`` package until it outgrows a flat list - a rename then, when there are eight or so
modules or two of them want the same name. The modules are exported rather than their
names, so two libraries can both have a ``Spec``."""

from . import ducts, gridfinity, gridfinity3d, print

__all__ = ["ducts", "gridfinity", "gridfinity3d", "print"]
