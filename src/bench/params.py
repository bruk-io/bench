"""Params: a script's settings as one frozen dataclass, and what a host does with one.

A script says what a person may change as a plain dataclass - every field a scalar with a
default, so ``Settings()`` is the defaults - and :func:`knob` puts a panel's hints on a field
without changing its type::

    @dataclass(frozen=True, slots=True, kw_only=True)
    class Cabinet:
        units_x: int = knob(4, min=1, max=7, label="Units across")
        tab: Literal["none", "full"] = "full"

:func:`declared` reads such a class into the :class:`~bench.scene.ParamView` records a panel
draws, before anything is built. :func:`configured` turns an untrusted mapping of names to
values - a panel's table, JSON off a wire, a dict in a test - into an instance, each value
coerced to its field's type and held inside its range, or says which field it could not read.
:func:`values_of` reads an instance back.

Nothing here runs a script or knows that one exists: a class and data in, data out. That is
why a value is held to its range here, once, rather than by each host that sends one.
"""

import math
from collections.abc import Mapping
from dataclasses import MISSING, Field, fields, is_dataclass
from dataclasses import field as _field
from typing import Any, Literal, NamedTuple, get_args, get_origin

from .scene import Kind, ParamView, Scalar


class _Hints(NamedTuple):
    """What a panel shows beside a field: its label, and the range and step of a number."""

    label: str | None
    min: float | None
    max: float | None
    step: float | None


_HINTS = "bench.knob"
"""The metadata key :func:`knob` files a field's :class:`_Hints` under."""

_NO_HINTS = _Hints(None, None, None, None)
"""The hints of a field declared with a bare default rather than a :func:`knob`."""


class _Slot(NamedTuple):
    """One field of a settings class, as this module reads it."""

    name: str
    kind: Kind
    default: Scalar
    hints: _Hints
    choices: tuple[Scalar, ...] | None


def knob[T: Scalar](
    default: T,
    *,
    label: str | None = None,
    min: float | None = None,
    max: float | None = None,
    step: float | None = None,
) -> T:
    """A settings field with a panel's hints on it: ``label``, and the ``min``, ``max`` and
    ``step`` of a number.

    The field's type is still ``default``'s own, so ``units_x: int = knob(4, min=1)`` is an
    ``int`` everywhere it is read. The range is not a suggestion: :func:`configured` holds a
    value outside it at the nearer end, and :func:`declared` refuses a default outside it,
    because that is the script's own mistake rather than something a panel sent.
    """
    return _field(default=default, metadata={_HINTS: _Hints(label, min, max, step)})


def declared(cls: type) -> list[ParamView]:
    """Every field of ``cls`` as the record a panel draws, in the order the class says them.

    The label falls back to the field's name, and a ``Literal`` field is a menu of its values.
    A class that is not settings is refused rather than half-read: a ``TypeError`` if it is not
    a dataclass or a field has no default or is not a ``bool``, ``int``, ``float``, ``str`` or
    ``Literal`` of one of those, and a ``ValueError`` if a default is outside its own range.
    """
    return [
        ParamView(
            name=slot.name,
            label=slot.name if slot.hints.label is None else slot.hints.label,
            kind=slot.kind,
            default=slot.default,
            min=slot.hints.min,
            max=slot.hints.max,
            step=slot.hints.step,
            choices=None if slot.choices is None else list(slot.choices),
        )
        for slot in _slots(cls)
    ]


def configured[P](cls: type[P], values: Mapping[str, object]) -> P:
    """``cls`` built from ``values``.

    Each name ``cls`` declares is coerced to its field's type - a number off a wire may have
    lost its integerness, a flag may arrive as the word a form sends. A number outside its
    range is held at the nearer end rather than refused, so a run never stops for one and the
    instance says what was built. A field ``values`` leaves out keeps its default, and a name
    ``cls`` does not declare is ignored: a table kept from an older version of the script is
    not a mistake.

    A value that is not one its field's type can read, or is not one of its choices, is a
    ``ValueError`` naming the field - there is no nearer end of ``"wide"`` to hold it at. A
    ``cls`` that is not a settings class at all is refused as :func:`declared` refuses it.
    """
    chosen = {
        slot.name: _read(slot, values[slot.name]) for slot in _slots(cls) if slot.name in values
    }
    return cls(**chosen)


def values_of(settings: object) -> dict[str, Scalar]:
    """What an instance of a settings class holds, by field name, in the class's order.

    Raises:
        TypeError: if ``settings`` is not a dataclass instance.
    """
    if isinstance(settings, type) or not is_dataclass(settings):
        msg = f"{settings!r} is not an instance of a settings dataclass"
        raise TypeError(msg)
    return {one.name: getattr(settings, one.name) for one in fields(settings)}


# ---- reading the class ---------------------------------------------------------------


def _slots(cls: type) -> tuple[_Slot, ...]:
    """Every field of ``cls``, read and checked.

    Raises:
        TypeError: if ``cls`` is not a dataclass.
    """
    if not (isinstance(cls, type) and is_dataclass(cls)):
        msg = f"{cls!r} is not a dataclass; a script's settings are one frozen dataclass"
        raise TypeError(msg)
    return tuple(_slot(cls.__name__, one) for one in fields(cls))


def _slot(owner: str, one: Field[Any]) -> _Slot:
    """One field of the class called ``owner``, as a :class:`_Slot`.

    The default is read as the field's type, so an ``int`` default on a ``float`` field is
    declared as the float it will be. A value a panel sends is held inside its range; a default
    is not, because a default outside its own range is the script contradicting itself, and
    quietly building something else would hide that.

    Raises:
        TypeError: if the field has no plain default, or its default is not of its type.
        ValueError: if its default is outside its own range.
    """
    where = f"{owner}.{one.name}"
    if one.default is MISSING:
        msg = f"{where} has no default; every setting needs one, so {owner}() is the defaults"
        raise TypeError(msg)
    kind, choices = _kind(where, one.type)
    if not _fits(kind, one.default, choices):
        msg = f"{where} defaults to {one.default!r}, which is not a {kind}"
        raise TypeError(msg)
    hints: _Hints = one.metadata.get(_HINTS, _NO_HINTS)
    slot = _Slot(one.name, kind, one.default, hints, choices)
    default = _read(slot, one.default)
    if default != one.default:
        msg = f"{where} defaults to {one.default!r}, outside its own range {_range(hints)}"
        raise ValueError(msg)
    return slot._replace(default=default)


def _range(hints: _Hints) -> str:
    """A range in words, as an error message says it: "1 to 5", "at least 1", "at most 5"."""
    if hints.min is not None and hints.max is not None:
        return f"{hints.min} to {hints.max}"
    if hints.min is not None:
        return f"at least {hints.min}"
    return f"at most {hints.max}"


def _fits(kind: Kind, default: object, choices: tuple[Scalar, ...] | None) -> bool:
    """Whether ``default`` is already a value of ``kind``: an ``int`` counts as a ``float``,
    as it does to a type checker, and a ``bool`` counts as neither number."""
    match kind:
        case "bool":
            return isinstance(default, bool)
        case "int":
            return isinstance(default, int) and not isinstance(default, bool)
        case "float":
            return isinstance(default, int | float) and not isinstance(default, bool)
        case "str":
            return isinstance(default, str)
        case "choice":
            return choices is not None and type(default) is type(choices[0])


def _kind(where: str, annotation: object) -> tuple[Kind, tuple[Scalar, ...] | None]:
    """Which widget a field's type asks for, and the menu when it is a ``Literal``.

    ``bool`` is its own kind, not an ``int``, and a ``Literal`` is a menu only when every
    value on it is the same one of the four scalar types.

    Raises:
        TypeError: if the type is none of those.
    """
    simple: dict[object, Kind] = {bool: "bool", int: "int", float: "float", str: "str"}
    if annotation in simple:
        return simple[annotation], None
    if get_origin(annotation) is Literal:
        choices = get_args(annotation)
        if (
            choices
            and len({type(choice) for choice in choices}) == 1
            and type(choices[0]) in simple
        ):
            return "choice", choices
    msg = (
        f"{where} is {annotation!r}; a setting is a bool, an int, a float, a str, or a Literal"
        " of one of those"
    )
    raise TypeError(msg)


# ---- reading a value -----------------------------------------------------------------


def _read(slot: _Slot, value: object) -> Scalar:
    """``value`` as ``slot``'s type, held inside its range and checked against its choices -
    each refusal a ``ValueError`` naming the field, from the reader that found it."""
    match slot.kind:
        case "bool":
            read: Scalar = _as_bool(slot.name, value)
        case "int":
            read = round(_as_number(slot.name, value))
        case "float":
            read = _as_number(slot.name, value)
        case "str":
            read = str(value)
        case "choice":
            assert slot.choices is not None  # a choice kind is only ever made with its menu
            read = _as_choice(slot.name, value, slot.choices)
    return _clamped(read, slot.hints)


def _as_choice(name: str, value: object, choices: tuple[Scalar, ...]) -> Scalar:
    """``value`` as one of ``choices``, read as the type they all are.

    Raises:
        ValueError: if it is not one of them.
    """
    match choices[0]:
        case bool():
            read: Scalar = _as_bool(name, value)
        case int():
            read = round(_as_number(name, value))
        case float():
            read = _as_number(name, value)
        case str():
            read = str(value)
    if read not in choices:
        listed = ", ".join(repr(choice) for choice in choices)
        msg = f"{name} must be one of {listed}, not {value!r}"
        raise ValueError(msg)
    return read


_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off", ""})


def _as_bool(name: str, value: object) -> bool:
    """``value`` as a flag, reading the words a form sends as well as the thing itself.

    Raises:
        ValueError: naming the field, if a string says neither yes nor no.
    """
    if isinstance(value, str):
        said = value.strip().lower()
        if said in _TRUE:
            return True
        if said in _FALSE:
            return False
        msg = f"{name} must be true or false, not {value!r}"
        raise ValueError(msg)
    return bool(value)


def _as_number(name: str, value: object) -> float:
    """``value`` as a finite number.

    Raises:
        ValueError: naming the field, if it is not a number, not the text of one, or not
            finite - an emptied field arrives as ``""``, and ``"nan"`` reads as a float.
    """
    if not isinstance(value, bool | int | float | str):
        msg = f"{name} must be a number, not {value!r}"
        raise ValueError(msg)
    try:
        number = float(value)
    except ValueError:
        msg = f"{name} must be a number, not {value!r}"
        raise ValueError(msg) from None
    if not math.isfinite(number):
        msg = f"{name} must be a finite number, not {value!r}"
        raise ValueError(msg)
    return number


def _clamped(value: Scalar, hints: _Hints) -> Scalar:
    """``value`` held inside the range its hints give: at the nearer end when it is outside.

    A flag and text have no range. A number keeps its type, so a float field held at an
    ``int`` end is still a float, and an int field held at a fractional end rounds *inward* -
    up from a low end, down from a high one - so what it is held at is still inside.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return value
    low, high = hints.min, hints.max
    if low is not None and value < low:
        return math.ceil(low) if isinstance(value, int) else float(low)
    if high is not None and value > high:
        return math.floor(high) if isinstance(value, int) else float(high)
    return value
