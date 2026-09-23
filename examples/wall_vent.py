"""A wall vent frame and the attachment that fits over its collar, put together by a face.

The frame is screwed over a hole in the wall: a flange with a window in it and a collar
standing out of its front face round the window. The attachment is a plate whose groove fits
over the collar at a sliding fit, with a funnel from the square window to a round duct on its
front - at 45 degrees across the square's corners, so it prints without supports.

The attachment is drawn where it prints - back face down on the bed, at the origin - and not
where it sits. `mated` puts it there: its back face on the flange's front face, touching, both
faces' frames drawn from the same corner so nothing has to be said about offset or spin. What
it hands back is the part the assembly shows, so a finding about the pair lands on the
attachment, and printed it says what it measured against what it was asked. Moving it has not
changed how it prints: it went up by the flange's thickness and turned not at all.

The groove round the collar is the second pair, and it is not solved for - it is checked,
with `check_fit`, which says how far apart the two really are against the slide the table
asks. The groove's corners are internal arcs, so it is drawn at `clearance(Fit.SLIDE, PLA,
concave=True)`: a concave arc is meshed as chords lying inside its circle, and a groove drawn
at the bare figure measures a thousandth or two under it once the kernel has built it.

A trim of a bigger vent - a 12.5 inch frame for the H2D with a hook lip the attachment drops
onto, sixteen magnets and four countersunk screws - with all three left out, so it builds
quickly.
"""

from dataclasses import dataclass

from bench import *
from bench.library.print import H2D, PLA, clearance

stock = Printed(PLA)  # both parts print back face down, everything else standing up off it
gap = clearance(Fit.SLIDE, PLA, concave=True)  # per side, between the collar and the groove


@dataclass(frozen=True, slots=True, kw_only=True)
class Vent:
    """The frame, its collar, and the attachment's plate and duct."""

    size: float = knob(120.0, min=60.0, max=300.0, step=5.0, label="Outside")
    corner: float = knob(6.0, min=1.0, max=20.0, step=0.5, label="Corner radius")
    flange: float = knob(6.0, min=3.0, max=20.0, step=0.5, label="Flange thickness")
    collar_inset: float = knob(15.0, min=5.0, max=50.0, step=1.0, label="Collar inset")
    collar_wall: float = knob(5.0, min=2.0, max=20.0, step=0.5, label="Collar wall")
    collar_depth: float = knob(12.0, min=5.0, max=40.0, step=1.0, label="Collar depth")
    base: float = knob(5.0, min=2.0, max=15.0, step=0.5, label="Attachment plate")
    duct: float = knob(50.0, min=20.0, max=150.0, step=5.0, label="Duct")
    spigot: float = knob(20.0, min=5.0, max=60.0, step=1.0, label="Spigot length")
    shell: float = knob(2.4, min=1.2, max=6.0, step=0.2, label="Funnel wall")


def _square(side: float, inset: float, r: float) -> Wire:
    """A rounded square `side` across, `inset` in from the frame's corner."""
    return rounded_rect(side, side, r, Point(inset, inset))


def _window(p: Vent) -> tuple[float, float]:
    """How far in from the corner the window starts, and how wide it is."""
    inset = p.collar_inset + p.collar_wall
    return inset, p.size - 2 * inset


def frame(p: Vent) -> tuple[Solid, Solid]:
    """The frame, and its collar on its own - what the attachment's groove must clear."""
    inset, side = _window(p)
    window = _square(side, inset, p.corner)
    plate = extrude(face(_square(p.size, 0.0, p.corner), holes=(window,)), p.flange, label="flange")
    ring = _square(p.size - 2 * p.collar_inset, p.collar_inset, p.corner)
    collar = extrude(
        face(ring, holes=(window,), on=raised(XY, p.flange)), p.collar_depth, label="collar"
    )
    return union(plate, collar), collar


def attachment(p: Vent) -> Solid:
    """The attachment as it prints: back face on the bed at the origin, the groove cut up
    into it, the funnel and the spigot standing off its front."""
    groove_top = p.collar_depth + gap
    body_top = groove_top + p.base
    body = extrude(fill(_square(p.size, 0.0, p.corner)), body_top, label="base")

    width = p.size - 2 * p.collar_inset + 2 * gap
    groove = _square(width, p.collar_inset - gap, p.corner + gap)
    body = cut(body, extrude(fill(groove, on=raised(XY, -0.5)), groove_top + 0.5), label="groove")

    inset, side = _window(p)
    centre = Point(p.size / 2, p.size / 2)
    r_out = p.duct / 2
    r_in = r_out - p.shell
    rise = side / 2 * 2**0.5 - r_out  # 45 degrees across the corners, which lean the most
    top = body_top + rise
    inner_bottom = _square(side, inset, p.corner)
    outer = loft(
        fill(offset(inner_bottom, p.shell), on=raised(XY, body_top)),
        fill(circle(r_out, centre), on=raised(XY, top)),
        label="transition",
    )
    inner = loft(
        fill(inner_bottom, on=raised(XY, body_top - 0.5)),
        fill(circle(r_in, centre), on=raised(XY, top + 0.5)),
    )
    spigot = extrude(
        face(circle(r_out, centre), holes=(circle(r_in, centre),), on=raised(XY, top)),
        p.spigot,
        label="spigot",
    )
    body = cut(union(body, union(outer, spigot)), inner, label="funnel")
    return cut(
        body,
        extrude(fill(inner_bottom, on=raised(XY, groove_top - 0.5)), p.base + 1.0),
        label="window",
    )


def build(p: Vent) -> Assembly:
    body, collar = frame(p)
    held = part("frame", body, stock)
    loose = part("attachment", attachment(p), stock)

    # The back face on the flange's front: `mated` moves the attachment there and measures
    # the pair it was asked for - a contact - and the part it hands back is what is shown.
    fitted = mated(held, ref("frame/flange/top"), loose, ref("attachment/base/bottom"))
    print(fitted)
    # The groove round the collar: not solved for, checked where the mate put it.
    print(
        f"attachment/groove round frame/collar: {check_fit(fitted.part.shape, collar, Fit.SLIDE, PLA)}"
    )

    for one in (held, fitted.part):
        check_fits(one.shape, H2D)
    print(f"frame {p.size:.0f} mm square, flange {p.flange:.1f} mm; groove {gap:.2f} mm a side")
    return assembly("vent", (Placed(held, XY), Placed(fitted.part, XY)), posed=True)


show(build)
