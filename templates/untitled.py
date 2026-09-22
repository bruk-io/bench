"""A new script: its settings, one part, and `show`.

Change a number in `Settings`, or drag it on the Parameters tab. Every script in the
Examples menu is a longer version of this one.
"""

from dataclasses import dataclass

from bench import *


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    """Everything a person can change, each with its label and range for the panel."""

    w: float = knob(100.0, min=20.0, max=400.0, step=1.0, label="Width")
    h: float = knob(60.0, min=20.0, max=400.0, step=1.0, label="Height")
    t: float = knob(3.0, min=1.0, max=12.0, step=0.5, label="Stock thickness")
    hole_r: float = knob(8.0, min=2.0, max=20.0, step=0.5, label="Hole radius")


def build(p: Settings) -> tuple[Part, ...]:
    # A plate with a round hole in the middle of it, named so a click on it gives its ref.
    hole = circle(p.hole_r, Point(p.w / 2, p.h / 2), label=Label("hole"))
    plate = face(rect(p.w, p.h), holes=(hole,))
    stock = Stock(p.t, "ply", kerf=0.25)
    return (part(Label("plate"), plate, stock, Process.LASER),)


show(build)
