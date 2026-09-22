"""One hinge stack of the sequential multi-pivot hinge in US 10,114,424 B2, at printable size.

The patent (Microsoft, "Multi-Pivot Hinge", Oct 2018) is the Surface Book's rolling hinge: a
chain of links on four parallel shafts that unrolls one axis at a time, so a laptop opens by
lengthening its own foot. What it discloses is a topology and an interlock rule, and not one
dimension - no millimetre, no radius, no angle beyond "obtuse". Every number in this script
is therefore this script's own, chosen for a 0.4 mm nozzle, and is recorded as such below.
Nothing here is the patent's figure and nothing here is a product.

**The mechanism, as the patent describes it (FIGS. 8, 9 and columns 4-6), and what this
script calls each piece.** A stack is a second-portion element (keyboard side; `base` here)
carrying a terminus with a passageway for the first shaft, then three links, then a
first-portion element (display side; `arm`). Each link has a first region with a circular
passageway and a second region with a D-profile passageway, joined by a central region, so
a keyed shaft is locked to one link's second region and turns freely in the next link's
first region - that pair of unlike passageways is the drive train, and two plain holes
would not be one. Three sequencing pins lie parallel to the
shafts, each in the channel of one link, and each is flanked by the previous body's second
region on one side and the next body's first region on the other. Cam surfaces on those
neighbours - the patent's 822(2) on a first region, 822(4) on a second region, 826 on the
terminus and 824 on the first-portion element - are pockets a pin can sink into. A pin in
the *fore* pocket locks the next link to this one; a pin in the *aft* pocket locks this
link to the previous one. The pockets only line up with the channel at the ends of a link's
travel, so a pin can only change pockets at the instant one axis finishes and the next is
due to start. Read the patent yourself before trusting this paragraph.

**Where this differs from the patent, on purpose.**

* The patent's shaft is D-shaped along its whole length inside the stack (FIG. 9 draws the
  flat in every section) and its circular passageway is simply a round hole the D turns in.
  That is what is built: one profile per shaft, not a round shaft with a keyed length.
* Each link's second region is two slabs deep rather than one, and sits directly on the
  slab below it, so the link prints on its first region with nothing overhanging. The
  patent's link is a Z in plan - one ring, a bar along the axis, one ring - which prints
  only with support under the far ring. The passageways, pockets and channel are unchanged.
* The patent limits each axis with rotation limiters riding on the keyed shafts outside the
  stack (FIGS. 5-6, `502`), which is why the shafts are keyed at all; the figures do not
  show their form. This demonstrator limits each axis inside the stack instead: a sector lug
  on every second region rides in a sector cutout of the next first region, and the two
  ends of the cutout are the stops. The shafts are still keyed as the patent says, but here
  the key carries nothing out to a limiter.
* Nothing retains a shaft at its far end; the head at the near end is the only shoulder.

**Every dimension is a choice, and here is where each came from.** The pins are 5 mm
because a 2 mm pin sliding in a printed channel is machined-metal territory (the owner's
reason for 2.5-3x device scale). The shaft is 6 mm with a flat one third of its radius
deep - deep enough to key in PLA. Every turning and sliding fit is
`clearance(Fit.SLIDE, PLA)` per side and every printed hole is widened by
`PLA.hole_compensation`, both from the print library, never typed - except the stop lug's
own concave inside, which asks `clearance(..., concave=True)` instead, so the chord sag of
its inner arc is in the fit rather than added on afterward. A ring keeps
`ring_wall` between its bore and the deepest pocket, which is what sizes the ring: its
radius is bore plus wall plus how far a pin sinks. The gap between two rings on the row is
1.4 pin radii - wider than a pin radius so the pocket is shallower than the pin's radius
(then a torque on the ring pushes the pin *out* of a round pocket rather than trapping it),
narrower than a pin diameter so a pin can never rest between two rings in neither pocket,
which would free two axes at once. A pin sinks a pin diameter minus that gap, plus a fit,
plus 0.3 mm of margin so the pin in one pocket clears the other ring by more than the
kernel's chord sag. All of that is arithmetic below, none of it is the patent's, and
none of it scales: make the stack bigger and the fits stay 0.2 mm, which is why there is
no scale knob.

**What is not verified, and cannot be here.** bench builds static bodies. There are no
joints, no constraints and no motion, so nothing in this script or in the checks it runs
proves that the pins lock and release in the patent's order. `deployment` poses the stack
by driving the four angles in the patent's sequence - the axis nearest the base flattens
first and the axis nearest the arm last, a path that opening walks from the closed end and
closing walks back from the open end, which is claim 1 - and places each pin in the pocket
that sequence says it is in; every pair of bodies is then measured - at the fit with
`check_clearance_within`, which walks the posed assembly by its parts' own labels, or, for
the four pairs where a shaft's head seats on its ring, as a declared contact with
`check_contact`, which asks whether the two share material rather than whether they stand
apart. The same two questions are then asked of the whole of the travel rather than of one
pose, with `check_clearance_through`: it builds the stack again at each of `samples`
deployments from closed to open, measures every pair at every one of them, and declares the
four seats at every one of them too. It **samples**, and what it hands back says so and at
what spacing - twenty-one poses, one every 0.05, is not "clear throughout", and a pair that
fouls between two of those poses is not found by it. Sampling rather than sweeping the
volumes is a deliberate choice: a hull of two poses holds the chord a point travels and not
the arc, so it is not even a conservative sweep, and a linkage sweeps through itself anyway -
a shaft and the link it is keyed to turn together and their swept volumes overlap completely
while the pair never meets at any instant. The measurement costs about a second per pose with
the app's modeller, which is why the count is a knob and not a constant. That shows the pose,
and the travel between poses, is *consistent*: every pin fits its pocket,
every ring clears the pin it is meant to pass, the four shoulders bear without biting into
what they bear on, and nothing else touches. It does not show the pin *moves* when it
should - that depends on the pocket camming the pin sideways against friction, which is a
mechanism question a printed stack has to answer on the desk. The patent's own text is
muddled at one point (it calls both the second and the fourth cam surface "in the first
region", and its Position Three prose names an axis its figure does not show turning); the
figure was followed where they disagreed.

Posing: `deployment` runs 0 (closed, every axis curled) to 1 (open, every axis flat).
FIG. 9's Position One is 0, Position Two is about 0.375 (first link flat, second turning)
and Position Three is about 0.7; 0.25, 0.5 and 0.75 are the handovers, where a pin has
both pockets in line and may cross.

The twelve parts are shown as one `posed` assembly, so the viewer draws each one where the
pose put it rather than laying them out in a row. Every one of them is a real part - it is
nested, checked and exported on its own, exactly as it would be in any other assembly; being
posed only says where they stand to be looked at. Nothing is fused into a thirteenth body to
carry the picture, which is what this script had to do before `Assembly.posed` existed.

Drawn as given means exactly that: the stack is modelled about its own axis, so it straddles
the grid plane rather than standing on it. Standing it up would be a layout by another name,
and would put the parts somewhere the clearances measured between them do not describe.
"""

import math
from dataclasses import dataclass

from bench import *
from bench.library.print import H2D, PLA, clearance


@dataclass(frozen=True, slots=True, kw_only=True)
class Stack:
    """How far open the stack is posed, and the sizes that set everything else."""

    deployment: float = knob(0.0, min=0.0, max=1.0, step=0.025, label="Deployment, closed to open")
    travel: float = knob(45.0, min=30.0, max=80.0, step=5.0, label="Travel per axis, degrees")
    shaft_d: float = knob(6.0, min=4.0, max=10.0, step=0.5, label="Shaft diameter")
    pin_d: float = knob(5.0, min=3.0, max=8.0, step=0.5, label="Sequencing pin diameter")
    ring_wall: float = knob(2.5, min=1.6, max=5.0, step=0.1, label="Wall round a bore")
    slab: float = knob(6.0, min=4.0, max=12.0, step=0.5, label="Ring thickness along the axis")
    # The cost is in the label because it is linear and a maker pays it on every run: a pose
    # is sixty-six measurements and about a second of modeller, so the top of this range is
    # most of a minute. Turning it down is a weaker claim, not a faster one, and the answer
    # says which claim was made.
    samples: int = knob(
        21, min=2, max=41, step=1, label="Poses measured, closed to open (~1s each)"
    )


pla = Printed(PLA, Orient(up=Y))  # everything prints with the hinge axis vertical
AXIS = Axis(ORIGIN, -Y)  # a positive turn about it takes +x toward +z: the way the stack curls
LUG_AT, LUG_SPAN = math.radians(220.0), math.radians(30.0)  # the stop lug, under and behind
MARGIN = 0.3  # how much more than a fit a pin in one pocket clears the other ring by
HEAD = 3.0  # a shaft's head, along the axis
BAR = 30.0  # how far the base and arm reach away from the stack


def section(outline: Wire, y0: float, y1: float, *, label: str | None = None) -> Solid:
    """``outline`` drawn in the x-z plane and swept from ``y0`` to ``y1`` along the axis."""
    on = plane(Point(0.0, y1, 0.0), -Y, X)
    return extrude(fill(outline, on=on), y1 - y0, label=label)


def sector(
    a0: float, a1: float, r0: float, r1: float, y0: float, y1: float, *, at: Point, label: str
) -> Solid:
    """The part of the annulus ``r0`` to ``r1`` round ``at`` between angles ``a0`` and ``a1``,
    swept ``y0`` to ``y1``. Built as a wedge across a ring, because an arc here only runs one
    way round and an annular sector needs one each way."""
    span, mid = a1 - a0, (a0 + a1) / 2
    reach = (r1 + 1.0) / math.cos(span / 4)
    x, z, _ = at
    wedge = polygon(
        (
            at,
            Point(x + reach * math.cos(a0), z + reach * math.sin(a0), 0.0),
            Point(x + reach * math.cos(mid), z + reach * math.sin(mid), 0.0),
            Point(x + reach * math.cos(a1), z + reach * math.sin(a1), 0.0),
        )
    )
    ring = cut(
        section(circle(r1, at), y0, y1, label="outer"),
        section(circle(r0, at), y0 - 1.0, y1 + 1.0),
        label="inner",
    )
    return name(common(ring, section(wedge, y0 - 1.0, y1 + 1.0, label="wedge")), label)


def posed_angles(travel: float, deployment: float) -> tuple[float, ...]:
    """The curl of each of the four axes, in radians, for a stack this far deployed.

    The deployment is spent flattening the axis nearest the base first and the one nearest
    the arm last, so at most one axis is ever between its ends: that is the sequence the
    pins enforce. The sequence is one path through the four angles, and claim 1's asymmetry
    is the direction it is walked: opening starts from the closed end, so the base's axis
    moves first; closing starts from the open end, so the arm's axis moves first. One value
    of ``deployment`` is one state on that path whichever way the stack is going, which is
    why there is no direction knob - closing to 0.4 and opening to 0.4 are the same stack.
    """
    curled: list[float] = []
    budget = 4 * travel * deployment
    for _ in range(4):
        taken = min(budget, travel)
        budget -= taken
        curled.append(travel - taken)
    return tuple(curled)


def build(p: Stack) -> Assembly:
    fit = clearance(Fit.SLIDE, PLA)  # per side: every turning fit, every sliding fit
    lug_fit = clearance(Fit.SLIDE, PLA, concave=True)  # the same, plus the lug's own sag
    comp = PLA.hole_compensation / 2  # per side: what a printed hole takes back
    r_s = p.shaft_d / 2
    flat = r_s - p.shaft_d / 6  # the D's flat, one third of the radius deep
    bore = r_s + fit + comp  # a bore the shaft turns or keys in, as drawn
    r_p = p.pin_d / 2
    pocket = r_p + fit + comp  # a pocket's radius, and the channel's half height
    gap = 1.4 * r_p  # between two rings along the row
    sink = 2 * r_p - gap + fit + MARGIN  # how far a pin sinks into a ring
    ring = bore + p.ring_wall + sink + fit + comp  # a ring's outside radius
    pitch = 2 * ring + gap  # shaft to shaft
    aft = ring - sink + r_p  # a pin's centre from the axis it is behind, in the aft pocket
    fore = pitch - ring + sink - r_p  # and in the fore pocket
    half = pocket + p.ring_wall  # half the channel block's height
    inner = bore + p.ring_wall  # inside radius of the stop lug and its cutout
    t = p.slab
    step = t + fit  # slab to slab along the axis
    c = math.radians(p.travel)
    eps = fit / inner  # the fit as an angle, at the cutout's tightest radius

    def pockets(body: Solid, *, aft_at: Point | None, fore_at: Point | None, y1: float) -> Solid:
        """``body`` with a pin pocket cut through it at each centre given."""
        for at, label in ((aft_at, "aft-cam"), (fore_at, "fore-cam")):
            if at is not None:
                body = cut(body, section(circle(pocket, at), -1.0, y1 + 1.0), label=label)
        return body

    def keyed(body: Solid, at: Point, y1: float, *, label: str) -> Solid:
        """``body`` with a D passageway cut through it round ``at``: the shaft's own profile
        plus the fit, drawn through `hole`'s ``profile=`` so the print compensation is added
        the same way it is added to a round bore's diameter, and not by hand.

        `shaft` draws its own D on `section`'s frame (mouth normal away from the axis, into
        the slab), while a bore needs `hole`'s frame (mouth normal out of the material,
        pointing back along the axis) so the depth `hole` fills in by default reaches the
        right way. The two frames read the same wire's "below centre" on opposite sides of
        the axis, so the profile is turned a half turn here - `d_bore` is symmetric left to
        right, so turning it is exactly flipping which side the flat lands on, and nothing
        else moves."""
        return hole(
            body,
            at,
            on=plane(Point(0.0, y1, 0.0), Y, X),
            profile=rotate(d_bore(r_s + fit, flat + fit), math.pi),
            printed=pla,
            label=label,
        )

    def free(body: Solid, at: Point, y1: float, *, label: str) -> Solid:
        """``body`` with a circular passageway through it round ``at``: a bore drawn by `hole`,
        which adds the print compensation itself."""
        return hole(
            body,
            at,
            on=plane(Point(0.0, y1, 0.0), Y, X),
            diameter=2 * (r_s + fit),
            printed=pla,
            label=label,
        )

    def cutout(body: Solid, at: Point, y1: float) -> Solid:
        """``body`` with the sector the previous body's lug swings through cut out of it."""
        tool = sector(
            LUG_AT - c - eps,
            LUG_AT + LUG_SPAN + eps,
            inner,
            ring + 2.0,
            -1.0,
            y1 + 1.0,
            at=at,
            label="stop",
        )
        return cut(body, tool, label="stop")

    def lug(at: Point, y0: float) -> Solid:
        """The stop lug standing on a second region whose top is at ``y0``, reaching one slab
        into the next body. It starts a millimetre down inside the ring rather than on its
        face, so the two never meet on a plane the kernel has to decide is one.

        This one is *not* a contact the clearance check forced, and `check_contact` does not
        free it. Standing the lug on the face instead was measured: it raises no clearance
        finding at all - the lug and the ring it stands on are one body, and `min_gap` is
        never asked about a body and itself - but it does raise an overhang, because the
        lug's outer arc then has nothing under it and leans 90 degrees off the build
        direction. The millimetre buys printability, not a passing check, so it stays.

        Its inside is a concave arc, and a concave arc is meshed as chords that lie inside
        the circle: the printed lug bulges inward by up to `CHORD`. `clearance(...,
        concave=True)` folds that sag into the fit itself, so `check_clearance` still reads
        the fit it asked for once this is meshed.
        """
        return sector(
            LUG_AT,
            LUG_AT + LUG_SPAN,
            inner + lug_fit,
            ring,
            y0 - 1.0,
            y0 + step,
            at=at,
            label="lug",
        )

    def link() -> Solid:
        """One link in its own frame: first region round the origin, second region round
        ``pitch`` along +x, the channel between them, and the lug on top."""
        second = Point(pitch, 0.0, 0.0)
        first = section(circle(ring), 0.0, t, label="first")
        body = union(first, section(circle(ring, second), 0.0, step + t, label="second"))
        block = section(
            rect(pitch - 2 * bore, 2 * half, Point(bore, -half, 0.0)),
            0.0,
            step + t,
            label="central",
        )
        body = union(union(body, block), lug(second, step + t))
        top = 2 * step + t
        body = free(body, ORIGIN, top, label="bore")
        body = keyed(body, second, top, label="keyed-bore")
        channel = section(
            rect(fore - aft + 2 * pocket, 2 * pocket, Point(aft - pocket, -pocket, 0.0)),
            -1.0,
            top + 1.0,
        )
        body = cut(body, channel, label="channel")
        body = pockets(
            body,
            aft_at=Point(pitch + aft, 0.0, 0.0),
            fore_at=Point(aft * math.cos(math.pi - c), aft * math.sin(math.pi - c), 0.0),
            y1=top,
        )
        return cutout(body, ORIGIN, top)

    def base() -> Solid:
        """The second-portion element: the terminus round the first shaft, keyed, with the
        aft pocket the first pin drops into, the lug that stops the first link, and a bar
        standing in for the keyboard side."""
        body = union(
            section(circle(ring), 0.0, t, label="terminus"),
            section(rect(BAR, 2 * half, Point(-BAR, -half, 0.0)), 0.0, t, label="bar"),
        )
        body = union(body, lug(ORIGIN, t))
        body = keyed(body, ORIGIN, step + t, label="keyed-bore")
        return pockets(body, aft_at=Point(aft, 0.0, 0.0), fore_at=None, y1=step + t)

    def arm() -> Solid:
        """The first-portion element: a first region round the fourth shaft, free, with the
        fore pocket the third pin holds it by, the cutout for the third link's lug, and a bar
        standing in for the display side."""
        body = union(
            section(circle(ring), 0.0, t, label="ring"),
            section(rect(BAR, 2 * half, Point(0.0, -half, 0.0)), 0.0, t, label="bar"),
        )
        body = free(body, ORIGIN, t, label="bore")
        body = pockets(
            body,
            aft_at=None,
            fore_at=Point(aft * math.cos(math.pi - c), aft * math.sin(math.pi - c), 0.0),
            y1=t,
        )
        return cutout(body, ORIGIN, t)

    def shaft(y0: float, y1: float) -> Solid:
        """A keyed shaft whose shank runs to ``y1`` out of a head that seats flat on ``y0``,
        where the first ring it passes through begins. The shank starts inside the head, for
        the same reason the lug starts inside its ring.

        The head's face and the ring's face are *coincident*, which is the shape a shoulder
        actually has: it bears on the ring, it does not hover a fit above it. This used to
        be drawn a fit short of ``y0`` - not because a shaft is made that way, but because
        `min_gap` reads a coincident pair as zero and `check_clearance` called that a
        failure. `check_contact` is what lets the geometry be right instead; the four seats
        are declared where the checks are run, below.
        """
        foot = y0 - HEAD
        return union(
            section(d_bore(r_s, flat), foot + 1.0, y1, label="shank"),
            section(circle(r_s + 1.5), foot, y0, label="head"),
        )

    def pin(x: float, y0: float, y1: float) -> Solid:
        return section(circle(r_p, Point(x, 0.0, 0.0)), y0, y1)

    def posed(body: Solid, turn: float, at: Point, y: float) -> Solid:
        """``body`` turned ``turn`` about its own axis and stood at ``at`` on the row, ``y``
        along the axis."""
        return move(rotate(body, turn, about=AXIS), Vector(at.x, y, at.z))

    # ---- the pose ----------------------------------------------------------------------
    slab_y = tuple(i * step for i in range(8))  # the eight rings along the axis
    one_link, one_arm, one_base = link(), arm(), base()  # each body once, posed many times

    def sequenced(deployment: float) -> tuple[tuple[float, ...], list[Point], tuple[bool, ...]]:
        """Each body's turn from the base at this deployment, where each axis then sits, and
        which pocket each pin is in.

        A pin is in the fore pocket while the next axis is still fully curled - that axis is
        what it holds locked - and in the aft pocket once the next axis has begun to open.
        """
        curled = posed_angles(c, deployment)
        turned = tuple(sum(curled[: n + 1]) for n in range(4))
        at = [ORIGIN]
        for turn in turned[:3]:
            at.append(at[-1] + Vector(pitch * math.cos(turn), 0.0, pitch * math.sin(turn)))
        return turned, at, tuple(curled[n + 1] >= c - 1e-9 for n in range(3))

    def stacked(deployment: float) -> tuple[Assembly, dict[str, Solid]]:
        """The twelve parts posed at ``deployment``, as the assembly they are shown as and
        their bodies by their own labels.

        One function so the pose a maker looks at and the poses ``check_clearance_through``
        samples are the same arithmetic rather than two readings of it.
        """
        turns, axes, in_fore = sequenced(deployment)
        parts: list[Placed] = []
        bodies: dict[str, Solid] = {}  # each part's own body by its own label

        def show_part(label: str, body: Solid) -> Solid:
            parts.append(Placed(part(label, body, pla), XY))
            bodies[label] = body
            return body

        show_part("base", one_base)
        for n in range(3):
            show_part(f"link-{n + 1}", posed(one_link, turns[n], axes[n], slab_y[2 * n + 1]))
        show_part("arm", posed(one_arm, turns[3], axes[3], slab_y[7]))
        for n in range(4):
            show_part(
                f"shaft-{n + 1}",
                posed(
                    shaft(slab_y[max(2 * n - 1, 0)], slab_y[2 * n + 1] + t),
                    0.0 if n == 0 else turns[n - 1],  # keyed to the body behind it
                    axes[n],
                    0.0,
                ),
            )
        for n in range(3):
            show_part(
                f"pin-{n + 1}",
                posed(
                    pin(fore if in_fore[n] else aft, slab_y[2 * n], slab_y[2 * n + 3] + t),
                    turns[n],
                    axes[n],
                    0.0,
                ),
            )
        return assembly("stack", tuple(parts), posed=True), bodies

    # ---- what is checked --------------------------------------------------------------
    # Every pair of the twelve, at the fit - sixty-six of them, sixty-two measured as gaps
    # and the other four as the seats they are. The pairs that carry the design are a pin
    # against the ring behind it (in the aft pocket, or clearing it), against the ring ahead
    # (the fore pocket, or clearing it) and against its own channel; a shaft against the
    # body it keys in and the one it turns in; and each body against the next, lug in
    # cutout and face to face. The other pairs cost nothing to ask and are the ones a
    # shorter list would have to argue are clear.
    # Four of those pairs are not meant to be clear at all: each shaft's head seats flat on
    # the first ring it passes through, and a shoulder that bears is the point of a shoulder.
    # Declaring a seat does not skip the pair - it changes the question. `check_clearance`
    # asks "are these `fit` apart", which a seated head can never be; `check_contact` asks
    # "do these two share material", which a seat satisfies and a collision does not. So a
    # head driven into its ring is still caught, as an overlap rather than as a short gap.
    # The four seats and the pairs left out of the clearance walk are one list read twice, so
    # neither can drift from the other: a pair this script excludes is a pair it has just
    # declared, by the parts' own labels rather than by which object happens to be which.
    seats = (
        ("base", "shaft-1"),
        ("link-1", "shaft-2"),
        ("link-2", "shaft-3"),
        ("link-3", "shaft-4"),
    )
    stack, bodies = stacked(p.deployment)
    for one, other in seats:
        check_contact(bodies[one], bodies[other])
    check_clearance_within(stack, fit, exclude=seats)
    # And then the same question asked of the whole travel rather than of this one pose,
    # which is the only version of it worth much: the pose where two rings foul each other
    # is exactly the pose nobody picked. `check_clearance_through` builds the stack again at
    # each of `samples` deployments from closed to open and measures all sixty-six pairs at
    # every one of them, declaring the same four seats at every one so a shoulder that bears
    # is not read as a collision sixty times over. It samples; it does not sweep, and what it
    # returns says so and at what spacing - printed below, because "clear at 21 poses" and
    # "clear throughout" are different claims and only the first one was ever made here.
    # None of this is about force, friction or binding: the pins still only sit where the
    # sequence says they sit, and nothing in bench moves one.
    through = check_clearance_through(
        lambda deployment: stacked(deployment)[0],
        fit,
        over=(0.0, 1.0),
        samples=p.samples,
        contacts=seats,
    )
    # No `check_wall` on the rings, and here is what it read when it was tried. Every
    # pocket meets a rim, and where the pocket's last chord crosses the rim's the boolean
    # leaves a strip of pocket wall a few hundredths of a millimetre wide. `check_wall`
    # measures from the middle of every triangle straight into the material, and from the
    # middle of that strip the material is a corner - 70 to 90 degrees of it - so the ray
    # is out of the ring within a fraction of a millimetre: it read 0.67 mm on the fore
    # pocket at these defaults and 0.08 mm on the aft pocket with a 3 mm pin, on the same
    # corner each time, and 2 mm on `ring_wall=4` only because the strip landed elsewhere.
    # A corner is not a wall, and the check cannot tell them apart. The walls that matter
    # are arithmetic - `ring_wall` from every bore to the deepest pocket and from the
    # channel to the block's edge, by construction - and are printed below instead.
    check_overhangs(bodies["link-1"], pla.orient, PLA)
    check_overhangs(bodies["shaft-1"], pla.orient, PLA)
    require(check_fits(bodies["base"], H2D))

    print(
        f"shaft {p.shaft_d:.1f} mm in a {2 * bore:.2f} mm bore, keyed on a flat {flat:.2f} mm below its axis"
    )
    print(
        f"pin {p.pin_d:.1f} mm in a {2 * pocket:.2f} mm channel; it sinks {sink:.2f} mm into a ring"
    )
    print(
        f"rings r {ring:.2f} on a {pitch:.2f} mm pitch; a pin rides {aft:.2f} to {fore:.2f} mm from its axis"
    )
    print(f"{p.ring_wall:.2f} mm from every bore to the deepest pocket, and round the channel")
    curl = posed_angles(c, p.deployment)
    _, _, in_fore = sequenced(p.deployment)
    degrees = ", ".join(f"{math.degrees(one):.0f}" for one in curl)
    where = ", ".join("fore" if one else "aft" for one in in_fore)
    print(f"deployed {p.deployment:.3f}: axes curled {degrees} deg; pins {where}")
    print(f"across the travel: {through}")
    print("the sequence is a pose here, not a mechanism: nothing in bench moves a pin")

    return stack


show(build)
