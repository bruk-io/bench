"""Script: the runtime the browser calls.

A script is ordinary Python that uses the :mod:`bench` vocabulary. It declares what a person
may change as one frozen dataclass, builds something from it in a function, and ends by
handing that function to :func:`show`::

    from dataclasses import dataclass

    from bench import *
    from bench.library import gridfinity

    @dataclass(frozen=True, slots=True, kw_only=True)
    class Cabinet:
        units_x: int = knob(4, min=1, max=7, label="Units across")

    def build(p: Cabinet) -> Build:
        return gridfinity.cabinet(gridfinity.Spec(units_x=p.units_x, drawers=6))

    show(build)

The run reads ``Cabinet``'s fields as its parameters and its overrides into a ``Cabinet`` -
see :mod:`bench.params` - and calls ``build`` with that. A script with nothing to change
shows what it made directly, as ``show(part)``.

:func:`run` executes one such script in a fresh namespace, collects what it said - what it
showed, the parameters it declared, the violations its checks found, what it printed on either
stream - and hands that to :mod:`bench.views`, which builds the :data:`bench.scene.Scene`. It
never raises for anything the script did wrong - a syntax error, an exception, a missing
:func:`show` - those come back as ``{"ok": False, "error": {...}}`` with the line number of the
script's own frame, so the editor can point at it.

``show`` is not a name of this module: each run builds its own as a closure over its own
notebook and injects it into the script's namespace. So two runs never see each other's
declarations, nothing global has to say which run is in flight, and a script that says
``from bench import *`` cannot replace it - the package does not export it.

A :class:`~bench.kernel.Kernel` is injected the same way and for the same reason: this
module names the protocol and never imports an implementation, so a run without one still
produces every ref, parameter and cut sheet and only leaves ``mesh`` empty.
"""

import builtins
import importlib
import inspect
import io
import linecache
import logging
import traceback
from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field, is_dataclass, replace
from types import FrameType, ModuleType
from typing import NamedTuple, TypeIs, assert_never

from . import views
from .checks import (
    Fitted,
    Sampled,
    Severity,
    Violation,
    clearance_between,
    contact_between,
    fit_between,
    fits,
    overhangs,
    sampling,
    unchecked,
    wall,
)
from .fasteners import CONTACT, Contact, Fit
from .geometry import XY, Vector
from .kernel import Kernel, Mesh
from .mate import UNMOVED, Mate, gap_of, mating
from .missing import explained
from .model import (
    Assembly,
    Build,
    Material,
    Orient,
    Part,
    Placed,
    Ref,
    Volume,
    assembly,
    ref,
)
from .nest import Bed
from .params import configured, declared, values_of
from .scene import ParamView, Scalar, Scene
from .telemetry import SILENT, Tracer, fields, timed
from .topology import Label, Shape, Solid
from .views import Finding

Showable = Assembly | Part | tuple[Part, ...] | Build
"""What a script may show: an assembly, one part, a tuple of parts, or a library's build."""

_FILENAME = "<script>"
"""The pseudo filename a script is compiled under - how its frames are told apart."""

_SCRIPT_NAME = "__script__"
"""``__name__`` inside a script: not ``__main__``, because nothing ran it from a shell."""

_BED = Bed(320.0, 320.0)
"""The laser bed a scene nests onto until :func:`run` is told otherwise, in millimetres."""


# ---- what one run collects -----------------------------------------------------------


class _Show(NamedTuple):
    """What :func:`show` was handed, in the one form the scene is built from."""

    assembly: Assembly
    quantities: Mapping[Ref, int]
    files: Mapping[str, str]


@dataclass(slots=True)
class _Recorder:
    """One run's notebook: the overrides it was given, and what the script told it.

    Written in as the script runs, which is what a notebook is for - ``shown`` is whatever
    the script showed, or ``None`` until it does. A fresh one is made for every :func:`run`
    and dropped at the end of it, which is why no declaration can outlive the run that made
    it.
    """

    overrides: Mapping[str, object]
    declared: list[ParamView] = field(default_factory=list)
    values: dict[str, Scalar] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    mates: list[tuple[Solid, Solid]] = field(default_factory=list)
    shown: _Show | None = None


# ---- what a script hands the run -----------------------------------------------------


def _shown(recorder: _Recorder, thing: object) -> None:
    """What the script showed, written into ``recorder``.

    A function is a build rather than a thing: it is called with the settings its one
    argument is annotated with, read from this run's overrides, and what it returns is what
    was shown. All of that happens inside the script's own ``show`` call, so a setting that is
    refused is reported at that line and an exception inside the build at the build's.

    Raises:
        ValueError: if the script already showed something.
    """
    if recorder.shown is not None:
        msg = "show() was already called; a script shows one thing"
        raise ValueError(msg)
    made = _built(recorder, thing) if _is_build(thing) else thing
    recorder.shown = _collected(_showable(made))


def _is_build(thing: object) -> TypeIs[Callable[..., object]]:
    """Whether ``show`` was handed a function to build with rather than a thing to show.

    A class is callable too and is not one: ``show(Settings)`` is a mistake, and
    :func:`_showable` is where it is named.
    """
    return callable(thing) and not isinstance(thing, type)


def _built(recorder: _Recorder, build: Callable[..., object]) -> object:
    """What ``build`` makes from this run's settings, with those settings declared first.

    The settings class comes off ``build``'s one argument. Its fields are written into
    ``recorder`` as the run's parameters and the overrides are read into an instance of it -
    a value outside its range is held at the nearer end, and one its field cannot read stops
    the run here, naming the field - and only then is ``build`` called with that instance.
    """
    settings = _settings_class(build)
    parameters = declared(settings)
    chosen: object = configured(settings, recorder.overrides)
    recorder.declared.extend(parameters)
    recorder.values.update(values_of(chosen))
    return build(chosen)


def _settings_class(build: Callable[..., object]) -> type:
    """The settings class ``build`` is written against: the annotation on its one argument.

    The annotation is evaluated in the script's own namespace, which is where the class was
    defined, so nothing has to be imported anywhere for it to be found.

    Raises:
        ValueError: if ``build`` does not take exactly one argument, or that argument is not
            annotated with a dataclass.
    """
    name = getattr(build, "__name__", "build")
    arguments = list(inspect.signature(build).parameters.values())
    if len(arguments) != 1:
        msg = (
            f"show({name}) calls {name} with the script's settings, so it takes one argument;"
            f" it takes {len(arguments)}"
        )
        raise ValueError(msg)
    hint = arguments[0].annotation
    if hint is inspect.Parameter.empty:
        msg = (
            f"show({name}) finds the settings class on {name}'s argument, which has no"
            f" annotation: write def {name}({arguments[0].name}: Settings)"
        )
        raise ValueError(msg)
    if not (isinstance(hint, type) and is_dataclass(hint)):
        msg = f"{name}'s argument is annotated {hint!r}, which is not a settings dataclass"
        raise ValueError(msg)
    return hint


def _recorded(
    recorder: _Recorder, found: Violation | None, subjects: tuple[Shape, ...]
) -> Violation | None:
    """A check's answer written into ``recorder`` with the line of the script that asked,
    and handed straight back so the script can act on it.

    ``subjects`` are the shapes the check was handed, kept beside the answer: a check runs on
    a bare solid, usually before the part it becomes exists, so this is the only moment the
    two can be tied together, and :mod:`bench.views` reads the part off it when the scene is
    built. Nothing is recorded when nothing was found: a scene's ``violations`` is what went
    wrong, not a transcript of what was asked.
    """
    if found is None:
        return None
    here = replace(found, line=_asking_line())
    recorder.findings.append(Finding(here, subjects))
    return here


class _Pair(NamedTuple):
    """Two of an assembly's bodies, and the labels of the parts they are.

    The labels travel with the bodies because a check made at a pose a script does not show
    has no other way to say which two parts it is about: :func:`bench.views.scene` matches a
    finding to a part by identity, and a body built at some sampled pose is not the very
    object any shown part holds.
    """

    one: str
    other: str
    a: Solid
    b: Solid


def _bodies(root: Assembly, asking: str) -> tuple[tuple[str, Solid], ...]:
    """Every part of ``root`` as its label and its body, in the order the assembly holds
    them.

    A part with no body cannot be measured at all, and dropping it would read as a pass for
    pairs nothing measured, so it stops the run instead.

    Raises:
        ValueError: naming the flat part that has no body to measure.
    """
    bodies: list[tuple[str, Solid]] = []
    for placed in root.parts:
        shape = placed.part.shape
        if not isinstance(shape, Solid):
            msg = (
                f"{asking} measures bodies, and {placed.part.label} is cut from"
                " sheet: a gap between two flat parts is not something a modeller can find"
            )
            raise ValueError(msg)
        bodies.append((str(placed.part.label), shape))
    return tuple(bodies)


def _named(
    root: Assembly,
    held: Container[str],
    pairs: Sequence[tuple[str | Label, str | Label]],
    asking: str,
    doing: str,
) -> tuple[frozenset[str], ...]:
    """The pairs ``pairs`` names, each as the two labels either way round, checked against
    the labels ``held`` holds.

    A label the assembly does not hold is a pair nobody skipped and nobody declared - the
    reading of it that carries on regardless would leave a maker believing something was
    said that was not - so it stops the run naming the label that is not there.

    Raises:
        ValueError: naming the label that is not a part of this assembly.
    """
    out: list[frozenset[str]] = []
    for one, other in pairs:
        named = (str(one), str(other))
        for label in named:
            if label not in held:
                msg = f"{asking} was told to {doing} {label!r}, which is not a part of {root.label}"
                raise ValueError(msg)
        out.append(frozenset(named))
    return tuple(out)


def _within(
    root: Assembly,
    exclude: Sequence[tuple[str | Label, str | Label]],
    asking: str = "check_clearance_within",
    *,
    mated: Sequence[tuple[Solid, Solid]] = (),
) -> tuple[_Pair, ...]:
    """Every pair of ``root``'s parts save the ones ``exclude`` names and the ones ``mated``
    holds, as the two bodies a clearance is measured between, in the order the assembly
    holds them.

    ``mated`` is the pairs a ``mated`` call has already put together and measured at the fit
    it was asked for - the very bodies, either way round, matched by identity like every
    finding - so a mated pair is declared by the call that made it and never asked a second,
    wrong question here.

    A pair is named by the two parts' own labels and either way round, and the bodies handed
    back are the parts' own shapes - the very objects - so a finding measured between them
    names both parts when :func:`bench.views.scene` puts it back together.

    A flat part, and a label ``exclude`` names that the assembly does not hold, both stop the
    run where :func:`_bodies` and :func:`_named` find them.
    """
    bodies = _bodies(root, asking)
    skip = set(_named(root, {label for label, _ in bodies}, exclude, asking, "leave out"))
    out: list[_Pair] = []
    for place, (label, body) in enumerate(bodies):
        for other, against in bodies[place + 1 :]:
            if frozenset((label, other)) not in skip and not _mated(body, against, mated):
                out.append(_Pair(label, other, body, against))
    return tuple(out)


def _mated(a: Solid, b: Solid, mated: Sequence[tuple[Solid, Solid]]) -> bool:
    """Whether ``a`` and ``b`` - these very objects, either way round - are a mated pair."""
    return any((a is one and b is other) or (a is other and b is one) for one, other in mated)


def _declared(
    root: Assembly, contacts: Sequence[tuple[str | Label, str | Label]], asking: str
) -> tuple[_Pair, ...]:
    """The pairs of ``root``'s parts that ``contacts`` names, as the two bodies a declared
    contact is measured between.

    The other half of :func:`_within` with the same ``exclude``: a pair a motion leaves out
    of its clearance walk is a pair it asks :func:`bench.checks.contact_between` about
    instead, at the same pose, so nothing goes unmeasured by being declared.

    A label ``contacts`` names that the assembly does not hold stops the run where
    :func:`_named` finds it, exactly as an ``exclude`` label does.
    """
    bodies = dict(_bodies(root, asking))
    _named(root, bodies, contacts, asking, "measure the contact of")
    return tuple(
        _Pair(str(one), str(other), bodies[str(one)], bodies[str(other)]) for one, other in contacts
    )


def _asking_line() -> int | None:
    """The line of the script that called in, found by walking out of :mod:`bench` until a
    frame belongs to the script itself.

    The script is compiled under :data:`_FILENAME`, so its frames are the ones that say so.
    ``None`` when none of them does - a check called from a library rather than from the
    script's own text.
    """
    frame: FrameType | None = inspect.currentframe()
    while frame is not None:
        if frame.f_code.co_filename == _FILENAME:
            return frame.f_lineno
        frame = frame.f_back
    return None


# ---- running -------------------------------------------------------------------------


_log = logging.getLogger(__name__)
"""This module's log records: one per run, saying how it ended."""


def run(
    source: str,
    overrides: Mapping[str, object] = frozendict(),
    *,
    bed: Bed = _BED,
    extras: Mapping[str, ModuleType] = frozendict(),
    reference: Mesh | None = None,
    kernel: Kernel | None = None,
    tracer: Tracer = SILENT,
    modules: Iterable[str] | None = None,
) -> Scene:
    """Run ``source`` as a script and return what it made, or why it failed.

    ``overrides`` replaces the default of any setting of the same name - read into the
    script's settings dataclass, coerced to each field's type and held to its range - which is
    how a panel edit re-runs a script without touching its text. ``bed`` is the stock
    everything is nested onto, margins and all. The script's ``show`` is built here, around
    this run's notebook, and injected into its namespace.

    ``kernel`` builds the bodies: with one, a part that is a :class:`~bench.topology.Solid`
    gets a ``mesh`` of triangles that each know the ref of the face they lie on, and an STL
    among the files. Without one, ``mesh`` is ``None`` and everything else - refs,
    parameters and cut sheets - comes out exactly the same, because none of that needs a body
    to be built.

    ``extras`` are modules to bind by name in that namespace as well - a host that wants
    ``gridfinity`` to mean :mod:`bench.library.gridfinity` without the script saying so
    passes ``{"gridfinity": gridfinity}``. A script that imports what it uses needs none of
    it, and that is the plainer way to write one.

    ``reference`` is a body somebody else made - a mesh read out of a file the host was
    handed - bound into the namespace under that name, so a script can measure what it is
    copying with :func:`bench.survey.survey` while it writes the thing that replaces it. It
    is a value rather than a module and so not one of ``extras``; it is ``None`` when the
    host has nothing to offer, which is what a script tests for. It reaches the scene as a
    body to draw behind the work - see :class:`~bench.scene.OkScene` - and nothing else in a
    run reads it: it is not a part, it is never shown, nested or exported.

    ``tracer`` is handed a span for the run and each stretch of it; the default keeps
    nothing. One log record says how each run ended.

    ``modules`` are the project's own other files, as their stems - what the caller mounted
    beside this one, if anything, the same list :func:`bench.shadow.shadowed` already checked
    them against. ``None`` is a caller with no project to speak of - a test of this function
    alone, say - and a plain ``ModuleNotFoundError`` reads exactly as Python left it. An
    empty sequence is a real answer, not a default standing in for one: a project that
    genuinely has no other files. Either way it says nothing about running the script -
    nothing here imports one for the script - and everything about failing to: with a project
    to ask, a ``ModuleNotFoundError`` also gets what :func:`bench.missing.explained` can say
    about it in the project's terms, so a maker sees "there is no sidekick.py" rather than
    only "No module named 'sidekick'".

    Nothing the script can do comes back as an exception: a syntax error, an exception it
    raised, a ``sys.exit()``, a ``show`` it never called or called twice all come back
    as an error scene. Only a bug in :mod:`bench` itself, or an interrupt from outside the
    script, can raise out of here.
    """
    with timed(tracer, "bench.run") as attributes:
        answer = _ran(source, overrides, bed, extras, reference, kernel, tracer, modules)
        attributes["bench.run.ok"] = answer["ok"]
    if answer["ok"]:
        _log.info(
            "run finished",
            extra=fields(
                **{
                    "bench.parts": len(answer["parts"]),
                    "bench.sheets": len(answer["sheets"]),
                    "bench.violations": len(answer["violations"]),
                }
            ),
        )
    else:
        error = answer["error"]
        line = {} if error["line"] is None else {"code.lineno": error["line"]}
        _log.warning("run failed: %s", error["message"], extra=fields(**line))
    return answer


def _ran(
    source: str,
    overrides: Mapping[str, object],
    bed: Bed,
    extras: Mapping[str, ModuleType],
    reference: Mesh | None,
    kernel: Kernel | None,
    tracer: Tracer,
    modules: Iterable[str] | None,
) -> Scene:
    """What :func:`run` does, each stretch of it a span of its own."""
    try:
        with timed(tracer, "bench.script.compile"):
            code = compile(source, _FILENAME, "exec")
    except SyntaxError as exc:
        # Nothing ran, so there is nothing either stream could hold yet.
        return views.failed(
            _message(exc), exc.lineno, "".join(traceback.format_exception_only(exc))
        )
    recorder = _Recorder(overrides)
    captured = io.StringIO()
    complained = io.StringIO()
    linecache.cache[_FILENAME] = (len(source), None, source.splitlines(keepends=True), _FILENAME)
    try:
        with (
            redirect_stdout(captured),
            redirect_stderr(complained),
            timed(tracer, "bench.script.exec"),
        ):
            # the script is the program; this is the interpreter
            exec(code, _namespace(recorder, extras, reference, kernel, tracer))
        shown = recorder.shown
        if shown is None:
            msg = "the script never called show(...), so there is nothing to look at"
            return views.failed(msg, None, "", captured.getvalue(), complained.getvalue())
        return views.scene(
            assembly=shown.assembly,
            quantities=shown.quantities,
            extra=shown.files,
            params=recorder.declared,
            values=recorder.values,
            findings=recorder.findings,
            bed=bed,
            kernel=kernel,
            reference=reference,
            stdout=captured.getvalue(),
            stderr=complained.getvalue(),
            tracer=tracer,
        )
    except (Exception, SystemExit) as exc:
        # SystemExit is not an Exception, but sys.exit() is something a script can say. The
        # `with` above has exited by now, so the buffers hold everything up to the raise.
        return views.failed(
            _message(exc, modules),
            _line(exc),
            _traceback(exc),
            captured.getvalue(),
            complained.getvalue(),
        )
    finally:
        linecache.cache.pop(_FILENAME, None)


def _namespace(
    recorder: _Recorder,
    extras: Mapping[str, ModuleType],
    reference: Mesh | None,
    kernel: Kernel | None,
    tracer: Tracer,
) -> dict[str, object]:
    """A fresh module-like namespace with the real builtins and the names a script starts
    with: ``show``, which it talks to the runtime through, the checks and the ``require`` that
    makes one fatal, ``mated``, which puts one part's face on another's and checks the pair,
    ``ref``, the package so ``from bench import *`` works, and whatever modules the host
    pre-bound in ``extras``.

    Every one of them is a closure over ``recorder`` - and, for the checks, over this run's
    ``kernel`` - so they are this run's own and nothing has to be installed anywhere to
    reach them. That is also how a check gets the modeller without :mod:`bench.checks`
    importing one. A library is not injected: a script imports what it uses, and ``extras``
    is only there for a host with scripts already written.
    """

    def show(thing: Showable | Callable[..., Showable]) -> None:
        """Hand the run what the script made: an :class:`~bench.model.Assembly`, a
        :class:`~bench.model.Part`, a sequence of parts, or a :class:`~bench.model.Build`,
        which is what :func:`bench.library.gridfinity.cabinet` returns.

        Or hand it the function that makes one from the script's settings -
        ``def build(p: Settings)``, shown as ``show(build)`` - and the run declares
        ``Settings``'s fields as its parameters and calls ``build`` with them read from its
        overrides.

        A script shows one thing, once.
        """
        _shown(recorder, thing)

    def check_fits(shape: Shape, volume: Volume) -> Violation | None:
        """Check that ``shape`` fits in ``volume``, and record what it finds.

        Needs no kernel: the tree's own bounds answer it, so this one runs in the browser
        as well as on the desk.
        """
        with timed(tracer, "bench.check.fits"):
            return _recorded(recorder, fits(shape, volume), (shape,))

    def check_clearance(a: Solid, b: Solid, least: float) -> Violation | None:
        """Check that two bodies stay ``least`` millimetres apart, and record what it
        finds."""
        with timed(tracer, "bench.check.clearance"):
            return _recorded(recorder, clearance_between(a, b, least, kernel=kernel), (a, b))

    def check_contact(a: Solid, b: Solid) -> Violation | None:
        """Declare that two bodies are meant to be in contact, check that they only touch
        rather than overlap, and record what it finds.

        The declaration *is* asking this instead of ``check_clearance`` for the pair: there
        is no reading of the geometry that makes a contact intentional, which is the whole
        point - a collision that happens to touch exactly still has to fail somewhere, and
        it fails here as an overlap or in ``check_clearance`` as a gap that came up short.
        """
        with timed(tracer, "bench.check.contact"):
            return _recorded(recorder, contact_between(a, b, kernel=kernel), (a, b))

    def check_clearance_within(
        assembly: Assembly,
        least: float,
        *,
        exclude: Sequence[tuple[str | Label, str | Label]] = (),
    ) -> tuple[Violation, ...]:
        """Check that every pair of ``assembly``'s parts stays ``least`` millimetres apart,
        save the pairs ``exclude`` names, and record what it finds.

        The assembly-shaped way to ask what a script otherwise writes as a loop over
        ``combinations``. It reads the parts off the assembly it was handed, so a pair is
        named by the two ``Part`` labels that are already there - ``("base", "shaft-1")``,
        either way round - rather than by two loose bodies a script has to keep hold of.
        Every finding is recorded exactly as ``check_clearance`` records one, and names both
        parts it is between; what comes back is the findings, so an empty tuple is a clean
        assembly.

        ``exclude`` is for the pairs that get ``check_contact`` instead: a shaft head seats
        on its ring, and asking whether the two stand apart is asking the wrong question of
        a shoulder. Leaving a pair out here is only half a declaration - the script still
        has to ask ``check_contact`` about it, or nothing measures that pair at all - so a
        label that is not a part of this assembly, and a part with no body to measure, both
        stop the run naming what was wrong rather than quietly checking something else.

        A pair ``mated`` put together is left out without being named here: the call that
        put it there declared it and measured it at the fit it asked for, and asking it again
        whether the two stand ``least`` apart would fail a contact that is right. That is by
        identity - the bodies ``mated`` handed back - so it holds whichever call came first.

        Every pair unless excluded, which is ``n(n-1)/2`` measurements: sixty-six for
        twelve bodies, and a bigger assembly than that has not been tried.
        """
        with timed(tracer, "bench.check.clearance_within"):
            found = tuple(
                _recorded(
                    recorder,
                    clearance_between(pair.a, pair.b, least, kernel=kernel),
                    (pair.a, pair.b),
                )
                for pair in _within(assembly, exclude, mated=recorder.mates)
            )
        return tuple(one for one in found if one is not None)

    def check_clearance_through(
        at: Callable[[float], Assembly],
        least: float,
        *,
        over: tuple[float, float] = (0.0, 1.0),
        samples: int,
        contacts: Sequence[tuple[str | Label, str | Label]] = (),
    ) -> Sampled:
        """Check that every pair of a moving assembly's parts stays ``least`` millimetres
        apart across the whole of ``over``, by building the assembly at ``samples`` poses
        along it and measuring each one, and record what it finds.

        ``at`` is the script's own "give me the assembly posed at this parameter" - the
        function whose one argument is the deployment, the angle, the fraction of travel the
        script drives its pose with. It is called once per sample, so it builds the geometry
        anew each time; that is the cost of asking about a motion rather than a picture.

        **This samples; it does not sweep, and the answer says so.** What comes back is a
        :class:`~bench.checks.Sampled`, whose sentence gives the number of poses and the
        spacing between them, because "clear at 21 poses" and "clear throughout" are
        different claims and only the first is ever made here. A pair that fouls between two
        samples is not found. Sampling is what this kernel can honestly do: a union of the
        poses is sampling with the samples glued together, a hull of two poses contains the
        chord a point travels and not the arc, so it is not even conservative, and there is
        no dilation in ``mesh``/``volume``/``min_gap`` to make one. Sweeping the volumes
        would also be the wrong question for a linkage, where two parts that move together
        sweep through each other while never meeting at any instant.

        ``contacts`` names the pairs that are meant to seat - a shaft head on its ring - and
        does both halves of that at every sample: the pair is left out of the clearance walk
        and asked ``contact_between`` instead, at that same pose. This is deliberately more
        than ``check_clearance_within``'s ``exclude``, which only leaves a pair out and
        trusts the script to declare it separately. A script never sees the poses this builds,
        so it *cannot* declare them itself, and a pair merely excluded here would go
        unmeasured through the whole motion.

        One finding per offending pair, at the first sample where it failed rather than one
        per sample, so a pair that fouls through half the travel is one line and not twenty.
        The finding names both parts and the parameter value in its own message: a body built
        at a sampled pose is not the very object any shown part holds, and
        :func:`bench.views.scene` matches a finding to a part by identity, so these findings
        carry no refs by construction.

        Nothing here is about force, friction or binding. A clean answer says the geometry of
        these poses does not interfere; it does not say the mechanism moves.
        """
        with timed(tracer, "bench.check.clearance_through"):
            poses = sampling(over, samples)
            # The first pose is built whether or not anything can measure it, so that a
            # sampling nobody could answer still refuses a label that is not a part and a
            # part that has no body. A browser with no modeller yet is exactly where a
            # mistyped seat would otherwise sit unnoticed until somebody ran it elsewhere.
            first = at(poses[0])
            _within(first, contacts, "check_clearance_through")
            _declared(first, contacts, "check_clearance_through")
            if kernel is None:
                note = _recorded(recorder, unchecked("clearance-through"), ())
                return Sampled(
                    least=least,
                    over=over,
                    samples=samples,
                    spacing=0.0,
                    findings=() if note is None else (note,),
                    measured=False,
                )
            failed: dict[frozenset[str], Violation] = {}
            for n, t in enumerate(poses):
                posed = first if n == 0 else at(t)
                where = (
                    f"at {t:.4f} of {over[0]:.3f} to {over[1]:.3f} (sample {n + 1} of {samples})"
                )
                asked = tuple(
                    (pair, clearance_between(pair.a, pair.b, least, kernel=kernel))
                    for pair in _within(posed, contacts, "check_clearance_through")
                ) + tuple(
                    (pair, contact_between(pair.a, pair.b, kernel=kernel))
                    for pair in _declared(posed, contacts, "check_clearance_through")
                )
                for pair, found in asked:
                    named = frozenset((pair.one, pair.other))
                    if found is None or named in failed:
                        continue
                    told = replace(
                        found, message=f"{pair.one} and {pair.other} {where}: {found.message}"
                    )
                    recorded = _recorded(recorder, told, ())
                    if recorded is not None:
                        failed[named] = recorded
        return Sampled(
            least=least,
            over=over,
            samples=samples,
            spacing=(over[1] - over[0]) / (samples - 1),
            findings=tuple(failed.values()),
            measured=True,
        )

    def mated(
        fixed: Solid | Part,
        at: str | Ref,
        moving: Part,
        onto: str | Ref,
        *,
        fit: Fit | Contact = CONTACT,
        offset: Vector = UNMOVED,
        spin: float = 0.0,
    ) -> Mate:
        """Put ``moving``'s face ``onto`` on ``fixed``'s face ``at`` at ``fit``, measure the
        pair at the fit it was asked for, and record what it finds.

        The placing is :func:`bench.mate.mating` - read it for ``offset``, ``spin`` and why
        the part's way up turns with it. The measuring is
        :func:`bench.checks.fit_between`, so the call that puts the two together is the one
        that checks them: a contact that turns out to overlap, or a fit that comes in
        tighter than it was asked, is recorded as a finding on the moved part - whose shape
        is the one a script shows, so the finding reaches it by identity. What comes back
        is the :class:`~bench.mate.Mate`: its ``part`` is what to put in the assembly, and
        printed it is the sentence - what was measured against what was asked.
        """
        with timed(tracer, "bench.check.mate"):
            mate = mating(fixed, at, moving, onto, fit=fit, offset=offset, spin=spin)
            body = mate.part.shape
            assert isinstance(body, Solid)  # mating refuses a part that is not a body
            fitted = fit_between(body, mate.on, fit, mate.gap, kernel=kernel)
            recorded = _recorded(recorder, fitted.finding, (body, mate.on))
            recorder.mates.append((body, mate.on))
            return replace(mate, fitted=replace(fitted, finding=recorded or fitted.finding))

    def check_fit(
        a: Solid, b: Solid, fit: Fit | Contact, material: Material | None = None
    ) -> Fitted:
        """Measure how ``a`` and ``b`` sit against the ``fit`` they are meant to have in
        ``material``, and record what it finds.

        The second pair of a mate: a mate puts a part in place by one pair of faces, and a
        groove round a collar beside it is not solved for - it is checked here, where the
        answer says how far apart the two really are against the fit's own gap. Printed,
        what comes back is that sentence; a fit tighter than asked is a finding on ``a``. A
        fit with no material to read its gap from stops the run, as
        :func:`bench.mate.gap_of` says.
        """
        with timed(tracer, "bench.check.fit"):
            fitted = fit_between(a, b, fit, gap_of(fit, material), kernel=kernel)
            recorded = _recorded(recorder, fitted.finding, (a, b))
            return replace(fitted, finding=recorded or fitted.finding)

    def check_wall(solid: Solid, least: float) -> Violation | None:
        """Check that every wall of ``solid`` is at least ``least`` millimetres thick, and
        record what it finds."""
        with timed(tracer, "bench.check.wall"):
            return _recorded(recorder, wall(solid, least, kernel=kernel), (solid,))

    def check_overhangs(solid: Solid, orient: Orient, material: Material) -> Violation | None:
        """Check that nothing on ``solid`` leans further off ``orient``'s build direction
        than ``material`` can hold up, and record what it finds."""
        with timed(tracer, "bench.check.overhangs"):
            return _recorded(recorder, overhangs(solid, orient, material, kernel=kernel), (solid,))

    def require(violation: Violation | None) -> None:
        """Stop the run if a check found something.

        Every ``check_`` above records and returns; this is the script's way of saying that
        one of them is not a warning but a condition of the part existing at all. Nothing
        found, nothing happens. A check that could not be answered - no kernel to measure
        with - does not stop the run either: ``UNCHECKED`` is not a failure, and a script
        that stopped on one would refuse to draw itself in a browser.

        Raises:
            ValueError: naming the check and what it found, which comes back as the error
                scene for the line that asked.
        """
        if violation is None or violation.severity is Severity.UNCHECKED:
            return
        raise ValueError(violation.message)

    return {
        "__name__": _SCRIPT_NAME,
        "__doc__": None,
        "__builtins__": builtins,
        "bench": _package(),
        "show": show,
        "ref": ref,
        "check_fits": check_fits,
        "check_clearance": check_clearance,
        "check_clearance_within": check_clearance_within,
        "check_clearance_through": check_clearance_through,
        "check_contact": check_contact,
        "check_fit": check_fit,
        "mated": mated,
        "check_wall": check_wall,
        "check_overhangs": check_overhangs,
        "require": require,
        "reference": reference,
        **extras,
    }


def _package() -> ModuleType:
    """The :mod:`bench` package itself, imported late: this module is part of it, so the
    name cannot be bound while it is still being defined."""
    return importlib.import_module(__name__.rpartition(".")[0])


# ---- what can be shown ---------------------------------------------------------------


def _showable(thing: object) -> Showable:
    """``thing`` as one of the things a script may show.

    A script is ordinary Python and its ``show`` is handed whatever it has, so what arrives
    here may be anything at all; this is where that becomes a closed union or an error.

    Raises:
        ValueError: if it is none of them.
    """
    match thing:
        case Assembly() | Part() | Build():
            return thing
        case type():
            msg = (
                f"show() was given the class {thing.__name__!r}; give it the function that"
                f" builds from it, as show(build)"
            )
            raise ValueError(msg)
        case tuple() | list():
            return _parts(thing)
        case _:
            msg = (
                f"show() cannot show {type(thing).__name__!r}: give it an assembly, a part, a"
                f" sequence of parts, or a build"
            )
            raise ValueError(msg)


def _parts(items: Sequence[object]) -> tuple[Part, ...]:
    """A loose sequence as the parts it holds.

    Raises:
        ValueError: if it is empty or holds anything but parts.
    """
    out: list[Part] = []
    for item in items:
        if not isinstance(item, Part):
            msg = f"show() was given a sequence holding {type(item).__name__!r}, not a part"
            raise ValueError(msg)
        out.append(item)
    if not out:
        msg = "show() was given an empty sequence, so there is nothing to look at"
        raise ValueError(msg)
    return tuple(out)


def _collected(thing: Showable) -> _Show:
    """``thing`` as the assembly, quantities and extra files a scene is built from."""
    match thing:
        case Assembly():
            return _Show(thing, frozendict(), frozendict())
        case Part():
            return _Show(assembly(thing.label, (Placed(thing, XY),)), frozendict(), frozendict())
        case Build(root, quantities, files):
            return _Show(root, quantities, files)
        case tuple():
            return _Show(_assembled(thing), frozendict(), frozendict())
        case _:
            assert_never(thing)


def _assembled(parts: tuple[Part, ...]) -> Assembly:
    """A loose tuple of parts as one assembly, each part laid on ``XY``."""
    return assembly(Label("parts"), tuple(Placed(one, XY) for one in parts))


# ---- failure -------------------------------------------------------------------------


def _message(exc: BaseException, modules: Iterable[str] | None = None) -> str:
    """The one line a status bar shows. A syntax error says its own complaint rather than
    ``str(exc)``, which would name the pseudo file the script was compiled under. A
    ``ModuleNotFoundError`` gets Python's own message plus what :func:`bench.missing.explained`
    can say about it in the project's terms, when there is a project to ask (``modules`` is
    not ``None``) and anything more honest to add."""
    if isinstance(exc, SyntaxError) and exc.msg:
        return f"{type(exc).__name__}: {exc.msg}"
    plain = f"{type(exc).__name__}: {exc}"
    if isinstance(exc, ModuleNotFoundError) and modules is not None:
        extra = explained(exc.name, modules)
        if extra is not None:
            return f"{plain} - {extra}"
    return plain


def _line(exc: BaseException) -> int | None:
    """Which line of the script was to blame: the last of its own frames, so an exception
    raised deep inside :mod:`bench` is still reported where the script called in.

    ``None`` when no frame was the script's - a failure in :mod:`bench` itself.
    """
    frames = _script_frames(exc)
    return frames[-1].lineno if frames else None


def _traceback(exc: BaseException) -> str:
    """The traceback as text, trimmed to the script's own frames: a user reading it should
    see their lines and the exception, not the machinery that ran them.

    A failure with no frame of the script's in it is shown whole, because then the
    machinery is the story.
    """
    frames = _script_frames(exc)
    if not frames:
        return "".join(traceback.format_exception(exc))
    lines = (
        "Traceback (most recent call last):\n",
        *traceback.format_list(frames),
        *traceback.format_exception_only(exc),
    )
    return "".join(lines)


def _script_frames(exc: BaseException) -> tuple[traceback.FrameSummary, ...]:
    return tuple(
        frame
        for frame in traceback.extract_tb(exc.__traceback__)
        if frame.filename == _FILENAME and frame.lineno is not None
    )
