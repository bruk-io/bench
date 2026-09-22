"""An open box, finger-jointed from ply, with a hole in one side and its name on the front.

The smallest useful script: its settings as one dataclass, one library call, one cut, one
engraving, and `show(build)`. Good first read before `gridfinity_cabinet.py`, and the one
`README.md` walks through.
"""

from dataclasses import dataclass

from bench import *


@dataclass(frozen=True, slots=True, kw_only=True)
class Box:
    """Everything a person can change, each with its label and range for the panel."""

    w: float = knob(120.0, min=40.0, max=400.0, step=1.0, label="Width")
    d: float = knob(80.0, min=40.0, max=400.0, step=1.0, label="Depth")
    h: float = knob(50.0, min=20.0, max=200.0, step=1.0, label="Height")
    t: float = knob(3.0, min=2.0, max=6.0, step=0.5, label="Stock thickness")
    hole_r: float = knob(10.0, min=3.0, max=30.0, step=0.5, label="Hole radius")
    label_size: float = knob(8.0, min=4.0, max=20.0, step=0.5, label="Label height")
    label_text: str = knob("screws", label="Engraved label")


def build(p: Box) -> tuple[Part, ...]:
    box = open_box(w=p.w, d=p.d, h=p.h, t=p.t, finger=12.0)

    # A round hole through one side, centred on it.
    side = cut(box.side_left, circle(p.hole_r, Point(p.d / 2, p.h / 2)), label=Label("hole"))

    # The label, centred on the front between its two side joints.
    width = text_width(p.label_text, p.label_size)
    at = Point((p.w - width) / 2, (p.h - p.label_size) / 2)
    label = Text(p.label_text, at, p.label_size, Label("label"))

    stock = Stock(p.t, "ply", kerf=0.25)
    return (
        part(Label("front"), box.front, stock, Process.LASER, engravings=(label,)),
        part(Label("back"), box.back, stock, Process.LASER),
        part(Label("side-left"), side, stock, Process.LASER),
        part(Label("side-right"), box.side_right, stock, Process.LASER),
        part(Label("bottom"), box.bottom, stock, Process.LASER),
    )


show(build)
