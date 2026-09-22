"""Unit: :mod:`bench.params` alone - a settings class read into the records a panel draws,
and a table of untrusted values read into an instance of it.

Every class here is declared in this file and nothing runs a script. What is asserted is the
contract a host relies on: the order and hints a panel draws, the coercion a value off a wire
needs, and which field is named when a value is refused.
"""

from dataclasses import dataclass
from typing import Literal

import pytest

from bench.params import configured, declared, knob, values_of

pytestmark = pytest.mark.unit


@dataclass(frozen=True, slots=True, kw_only=True)
class Panel:
    """A settings class with one field of every kind, hinted and not."""

    w: float = knob(80.0, min=10.0, max=200.0, step=0.5, label="Width")
    h: float = 40.0
    count: int = knob(4, min=1, max=7, label="Count")
    holes: bool = knob(True, label="Holes")
    finish: Literal["oil", "wax", "none"] = knob("oil", label="Finish")
    title: str = "panel"


# ---- declared ------------------------------------------------------------------------


def test_every_field_is_declared_in_the_order_the_class_says_it() -> None:
    assert [one["name"] for one in declared(Panel)] == [
        "w",
        "h",
        "count",
        "holes",
        "finish",
        "title",
    ]


def test_a_knob_records_its_hints_on_the_declaration() -> None:
    assert declared(Panel)[0] == {
        "name": "w",
        "label": "Width",
        "kind": "float",
        "default": 80.0,
        "min": 10.0,
        "max": 200.0,
        "step": 0.5,
        "choices": None,
    }


def test_a_bare_default_is_a_parameter_labelled_with_its_own_name() -> None:
    h = declared(Panel)[1]
    assert (h["label"], h["kind"], h["default"], h["min"], h["max"]) == (
        "h",
        "float",
        40.0,
        None,
        None,
    )


def test_each_scalar_type_asks_for_its_own_widget() -> None:
    kinds = {one["name"]: one["kind"] for one in declared(Panel)}
    assert kinds == {
        "w": "float",
        "h": "float",
        "count": "int",
        "holes": "bool",
        "finish": "choice",
        "title": "str",
    }


def test_a_literal_field_is_a_menu_of_its_values() -> None:
    finish = declared(Panel)[4]
    assert finish["choices"] == ["oil", "wax", "none"]
    assert finish["default"] == "oil"


def test_something_that_is_not_a_dataclass_is_not_settings() -> None:
    class Loose:
        w = 1.0

    with pytest.raises(TypeError, match="not a dataclass"):
        declared(Loose)


def test_a_field_without_a_default_is_refused_by_name() -> None:
    @dataclass(frozen=True)
    class Undecided:
        w: float

    with pytest.raises(TypeError, match=r"Undecided\.w has no default"):
        declared(Undecided)


def test_a_field_that_is_not_a_scalar_is_refused_by_name() -> None:
    @dataclass(frozen=True)
    class Nested:
        sizes: tuple[int, ...] = (1, 2)

    with pytest.raises(TypeError, match=r"Nested\.sizes is tuple\[int, \.\.\.\]"):
        declared(Nested)


def test_a_literal_of_mixed_types_is_not_a_menu() -> None:
    @dataclass(frozen=True)
    class Mixed:
        pick: Literal["one", 2] = "one"

    with pytest.raises(TypeError, match=r"Mixed\.pick"):
        declared(Mixed)


def test_a_default_outside_its_own_range_is_refused_rather_than_held() -> None:
    """A panel's value is held at the nearer end; a default is the script contradicting
    itself, and building something else would hide that."""

    @dataclass(frozen=True)
    class Contrary:
        n: int = knob(0, min=1, max=5)

    with pytest.raises(
        ValueError, match=r"Contrary\.n defaults to 0, outside its own range 1 to 5"
    ):
        declared(Contrary)


def test_an_int_default_on_a_float_field_is_declared_as_a_float() -> None:
    """``h: float = 40`` is fine to Python and to a type checker, so it is fine here too."""

    @dataclass(frozen=True)
    class Whole:
        h: float = 40

    default = declared(Whole)[0]["default"]
    assert (default, type(default)) == (40.0, float)


def test_a_default_that_is_not_of_its_field_type_is_refused_by_name() -> None:
    """A script is not type-checked before it runs, so the class is checked when it is read."""

    @dataclass(frozen=True)
    class Confused:
        n: int = "four"  # type: ignore[assignment]

    with pytest.raises(TypeError, match=r"Confused\.n defaults to 'four', which is not a int"):
        declared(Confused)


# ---- configured ----------------------------------------------------------------------


def test_no_values_is_the_defaults() -> None:
    assert configured(Panel, {}) == Panel()


def test_a_value_is_coerced_to_the_type_of_its_field() -> None:
    settings = configured(
        Panel, {"w": "120", "h": 55, "count": 3.0, "holes": "false", "finish": "wax", "title": 7}
    )
    assert settings == Panel(w=120.0, h=55.0, count=3, holes=False, finish="wax", title="7")


def test_an_int_field_holds_an_int_when_the_value_arrives_as_a_float() -> None:
    assert type(configured(Panel, {"count": 3.0}).count) is int


def test_a_name_the_class_does_not_declare_is_ignored() -> None:
    assert configured(Panel, {"gone": 1, "w": 90}) == Panel(w=90.0)


@pytest.mark.parametrize(
    ("values", "held"),
    [
        ({"count": 0}, {"count": 1}),
        ({"count": 8}, {"count": 7}),
        ({"count": "9.6"}, {"count": 7}),
        ({"w": 5}, {"w": 10.0}),
        ({"w": "999"}, {"w": 200.0}),
    ],
)
def test_a_number_outside_its_range_is_held_at_the_nearer_end(
    values: dict[str, object], held: dict[str, object]
) -> None:
    settings = values_of(configured(Panel, values))
    assert {name: settings[name] for name in held} == held


def test_a_float_held_at_its_end_is_still_a_float() -> None:
    assert type(configured(Panel, {"w": 5}).w) is float


def test_an_int_held_at_a_fractional_end_rounds_inward_and_stays_in_range() -> None:
    @dataclass(frozen=True)
    class Stepped:
        n: int = knob(2, min=1.5, max=4.5)

    low, high = configured(Stepped, {"n": 0}).n, configured(Stepped, {"n": 9}).n
    assert (low, high) == (2, 4)
    assert type(low) is int and type(high) is int


@pytest.mark.parametrize("value", ["", "wide", "nan", "inf", None])
def test_a_value_that_is_not_a_finite_number_is_refused_naming_the_field(value: object) -> None:
    """``""`` is what an emptied field sends; read as a number it used to be ``0``."""
    with pytest.raises(ValueError, match=r"^h must be a"):
        configured(Panel, {"h": value})


def test_a_flag_that_says_neither_yes_nor_no_is_refused() -> None:
    with pytest.raises(ValueError, match="holes must be true or false, not 'maybe'"):
        configured(Panel, {"holes": "maybe"})


def test_a_choice_that_is_not_on_the_menu_is_refused_with_the_menu() -> None:
    with pytest.raises(ValueError, match="finish must be one of 'oil', 'wax', 'none', not 'paint'"):
        configured(Panel, {"finish": "paint"})


def test_the_bad_field_is_the_one_named_even_when_others_are_fine() -> None:
    """An out-of-range number is held rather than refused, so the bad value here is one no
    field can read at all."""
    with pytest.raises(ValueError, match=r"^count must be a number, not 'lots'"):
        configured(Panel, {"w": 100, "count": "lots", "title": "ok"})


# ---- values_of -----------------------------------------------------------------------


def test_an_instance_reads_back_as_its_values_by_name() -> None:
    assert values_of(Panel(count=2)) == {
        "w": 80.0,
        "h": 40.0,
        "count": 2,
        "holes": True,
        "finish": "oil",
        "title": "panel",
    }


def test_values_of_a_class_rather_than_an_instance_is_refused() -> None:
    with pytest.raises(TypeError, match="not an instance"):
        values_of(Panel)
