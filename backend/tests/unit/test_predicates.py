"""Tests for the three-valued permit-rule predicate evaluator (SPEC.md section 7).

NOTE: every number in this file (1200, 500, 1000, ...) is an arbitrary TEST VALUE chosen
to exercise the logic. None of them is a real City of Irvine or state ADU rule.
"""

import builtins
import itertools
from pathlib import Path

import pytest

from clearpath.permits import predicates
from clearpath.permits.predicates import (
    ADU_FACT_SCHEMA,
    MAX_DEPTH,
    FactType,
    PredicateResult,
    PredicateValidationError,
    Tri,
    evaluate_predicate,
    to_status,
    validate_facts,
    validate_predicate,
)

S = ADU_FACT_SCHEMA

# Leaf predicates whose value is fixed by FACTS_FOR_TRI below.
# existing_dwelling=True  -> TRUE
# existing_dwelling=False -> FALSE
# existing_dwelling absent -> UNKNOWN
LEAF = {"eq": ["existing_dwelling", True]}


def leaf_for(tri: Tri, key: str):
    """A leaf predicate on `key` (a fact used only by this leaf) that evaluates to `tri`."""
    return {"eq": [key, True]}, {Tri.TRUE: True, Tri.FALSE: False, Tri.UNKNOWN: None}[tri]


# Two independent boolean facts so all/any can combine two different tri values.
TWO_BOOL_SCHEMA = {"a": FactType.BOOLEAN, "b": FactType.BOOLEAN}


def ev(pred, facts, schema=S):
    return evaluate_predicate(pred, facts, schema)


# --------------------------------------------------------------------------------------
# Truth tables
# --------------------------------------------------------------------------------------

ALL_TRI = [Tri.TRUE, Tri.FALSE, Tri.UNKNOWN]


@pytest.mark.parametrize(
    "inner, expected",
    [(Tri.TRUE, Tri.FALSE), (Tri.FALSE, Tri.TRUE), (Tri.UNKNOWN, Tri.UNKNOWN)],
)
def test_not_truth_table(inner, expected):
    pred, value = leaf_for(inner, "a")
    facts = {} if value is None else {"a": value}
    result = ev({"not": pred}, facts, TWO_BOOL_SCHEMA)
    assert result.value is expected
    assert result.missing_keys == (("a",) if expected is Tri.UNKNOWN else ())


def _all_expected(x, y):
    if Tri.FALSE in (x, y):
        return Tri.FALSE
    if Tri.UNKNOWN in (x, y):
        return Tri.UNKNOWN
    return Tri.TRUE


def _any_expected(x, y):
    if Tri.TRUE in (x, y):
        return Tri.TRUE
    if Tri.UNKNOWN in (x, y):
        return Tri.UNKNOWN
    return Tri.FALSE


@pytest.mark.parametrize("x, y", list(itertools.product(ALL_TRI, ALL_TRI)))
@pytest.mark.parametrize("op, expected_fn", [("all", _all_expected), ("any", _any_expected)])
def test_all_any_truth_tables(op, expected_fn, x, y):
    pa, va = leaf_for(x, "a")
    pb, vb = leaf_for(y, "b")
    facts = {k: v for k, v in (("a", va), ("b", vb)) if v is not None}
    result = ev({op: [pa, pb]}, facts, TWO_BOOL_SCHEMA)
    expected = expected_fn(x, y)
    assert result.value is expected
    if expected is Tri.UNKNOWN:
        want = tuple(sorted(k for k, t in (("a", x), ("b", y)) if t is Tri.UNKNOWN))
        assert result.missing_keys == want
    else:
        assert result.missing_keys == ()


def test_single_operand_all_and_any():
    assert ev({"all": [LEAF]}, {"existing_dwelling": True}).value is Tri.TRUE
    assert ev({"any": [LEAF]}, {"existing_dwelling": False}).value is Tri.FALSE


# --------------------------------------------------------------------------------------
# Comparison operators
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pred, facts, expected",
    [
        ({"eq": ["adu_form", "detached"]}, {"adu_form": "detached"}, Tri.TRUE),
        ({"eq": ["adu_form", "detached"]}, {"adu_form": "attached"}, Tri.FALSE),
        ({"eq": ["adu_form", "detached"]}, {}, Tri.UNKNOWN),
        ({"eq": ["adu_form", "detached"]}, {"adu_form": None}, Tri.UNKNOWN),
        ({"eq": ["existing_dwelling", True]}, {"existing_dwelling": True}, Tri.TRUE),
        ({"eq": ["existing_dwelling", True]}, {"existing_dwelling": False}, Tri.FALSE),
        ({"eq": ["floor_area_sqft", 500]}, {"floor_area_sqft": 500.0}, Tri.TRUE),
        ({"eq": ["floor_area_sqft", 500]}, {"floor_area_sqft": 501}, Tri.FALSE),
    ],
)
def test_eq(pred, facts, expected):
    result = ev(pred, facts)
    assert result.value is expected
    key = pred["eq"][0]
    assert result.missing_keys == ((key,) if expected is Tri.UNKNOWN else ())


# (operator, fact value, literal, expected) -- boundary cases at value == literal
ORDERING_CASES = [
    ("lt", 1199, 1200, Tri.TRUE),
    ("lt", 1200, 1200, Tri.FALSE),
    ("lt", 1201, 1200, Tri.FALSE),
    ("lte", 1199, 1200, Tri.TRUE),
    ("lte", 1200, 1200, Tri.TRUE),
    ("lte", 1201, 1200, Tri.FALSE),
    ("gt", 1201, 1200, Tri.TRUE),
    ("gt", 1200, 1200, Tri.FALSE),
    ("gt", 1199, 1200, Tri.FALSE),
    ("gte", 1201, 1200, Tri.TRUE),
    ("gte", 1200, 1200, Tri.TRUE),
    ("gte", 1199, 1200, Tri.FALSE),
    ("lt", 1199.5, 1200, Tri.TRUE),
    ("gte", 1200.0, 1200, Tri.TRUE),
]


@pytest.mark.parametrize("op, value, literal, expected", ORDERING_CASES)
def test_ordering_operators(op, value, literal, expected):
    result = ev({op: ["floor_area_sqft", literal]}, {"floor_area_sqft": value})
    assert result.value is expected
    assert result.missing_keys == ()


@pytest.mark.parametrize("op", ["lt", "lte", "gt", "gte"])
def test_ordering_operator_missing_fact(op):
    result = ev({op: ["floor_area_sqft", 1200]}, {"adu_form": "detached"})
    assert result.value is Tri.UNKNOWN
    assert result.missing_keys == ("floor_area_sqft",)


@pytest.mark.parametrize(
    "facts, expected",
    [
        ({"adu_form": "attached"}, Tri.TRUE),
        ({"adu_form": "detached"}, Tri.FALSE),
        ({}, Tri.UNKNOWN),
    ],
)
def test_in(facts, expected):
    result = ev({"in": ["adu_form", ["attached", "conversion"]]}, facts)
    assert result.value is expected
    assert result.missing_keys == (("adu_form",) if expected is Tri.UNKNOWN else ())


def test_in_with_numbers():
    assert ev({"in": ["floor_area_sqft", [500, 1000]]}, {"floor_area_sqft": 1000}).value is Tri.TRUE


# --------------------------------------------------------------------------------------
# missing_keys in nested cases
# --------------------------------------------------------------------------------------

DETACHED_SMALL = {"all": [{"eq": ["adu_form", "detached"]}, {"lt": ["floor_area_sqft", 1200]}]}


def test_nested_missing_floor_area_is_unknown():
    result = ev(DETACHED_SMALL, {"adu_form": "detached"})
    assert result == PredicateResult(Tri.UNKNOWN, ("floor_area_sqft",))


def test_nested_decided_false_has_no_missing_keys():
    result = ev(DETACHED_SMALL, {"adu_form": "attached"})
    assert result == PredicateResult(Tri.FALSE, ())


def test_nested_all_missing_collects_sorted_union():
    result = ev(DETACHED_SMALL, {})
    assert result == PredicateResult(Tri.UNKNOWN, ("adu_form", "floor_area_sqft"))


def test_any_decided_true_drops_missing_keys():
    pred = {"any": [{"eq": ["adu_form", "detached"]}, {"lt": ["floor_area_sqft", 1200]}]}
    assert ev(pred, {"adu_form": "detached"}) == PredicateResult(Tri.TRUE, ())


def test_deep_nesting_only_reports_keys_that_still_matter():
    # any[ all[form=detached, area<1200], all[dwelling=True, area<500] ]
    # dwelling=False makes the second branch FALSE, so its keys must not be reported.
    pred = {
        "any": [
            {"all": [{"eq": ["adu_form", "detached"]}, {"lt": ["floor_area_sqft", 1200]}]},
            {"all": [{"eq": ["existing_dwelling", True]}, {"lt": ["floor_area_sqft", 500]}]},
        ]
    }
    result = ev(pred, {"existing_dwelling": False})
    assert result == PredicateResult(Tri.UNKNOWN, ("adu_form", "floor_area_sqft"))


def test_missing_keys_are_deduplicated():
    pred = {"all": [{"gt": ["floor_area_sqft", 100]}, {"lt": ["floor_area_sqft", 1200]}]}
    assert ev(pred, {}).missing_keys == ("floor_area_sqft",)


def test_not_of_unknown_keeps_missing_keys():
    assert ev({"not": DETACHED_SMALL}, {"adu_form": "detached"}) == PredicateResult(
        Tri.UNKNOWN, ("floor_area_sqft",)
    )


# --------------------------------------------------------------------------------------
# C01-style case and to_status
# --------------------------------------------------------------------------------------

C01_FACTS = {"project_type": "adu", "adu_form": "detached", "existing_dwelling": True}


def test_c01_needs_information_where_floor_area_matters():
    area_rule = {
        "all": [
            {"eq": ["project_type", "adu"]},
            {"eq": ["adu_form", "detached"]},
            {"eq": ["existing_dwelling", True]},
            {"lte": ["floor_area_sqft", 1200]},
        ]
    }
    result = ev(area_rule, C01_FACTS)
    assert to_status(result) == "needs_information"
    assert result.missing_keys == ("floor_area_sqft",)


def test_c01_applies_where_floor_area_does_not_matter():
    rule = {"all": [{"eq": ["adu_form", "detached"]}, {"eq": ["existing_dwelling", True]}]}
    assert to_status(ev(rule, C01_FACTS)) == "applies"


def test_c01_not_applicable_only_when_decided_by_known_facts():
    rule = {"all": [{"eq": ["adu_form", "attached"]}, {"lte": ["floor_area_sqft", 1200]}]}
    assert to_status(ev(rule, C01_FACTS)) == "not_applicable"


def test_to_status_mapping():
    assert to_status(PredicateResult(Tri.TRUE, ())) == "applies"
    assert to_status(PredicateResult(Tri.FALSE, ())) == "not_applicable"
    assert to_status(PredicateResult(Tri.UNKNOWN, ("x",))) == "needs_information"


@pytest.mark.parametrize("op", ["eq", "lt", "lte", "gt", "gte"])
def test_missing_fact_never_becomes_not_applicable(op):
    for wrapper in (lambda p: p, lambda p: {"not": p}, lambda p: {"all": [p]}, lambda p: {"any": [p]}):
        pred = wrapper({op: ["floor_area_sqft", 1200]})
        assert to_status(ev(pred, {})) == "needs_information"


def test_result_is_frozen():
    result = ev(LEAF, {"existing_dwelling": True})
    with pytest.raises(Exception):
        result.value = Tri.FALSE  # type: ignore[misc]


# --------------------------------------------------------------------------------------
# Predicate validation errors
# --------------------------------------------------------------------------------------


def nest_not(depth: int):
    """A predicate exactly `depth` levels deep (root counts as level 1)."""
    node = LEAF
    for _ in range(depth - 1):
        node = {"not": node}
    return node


INVALID_PREDICATES = [
    ("unknown_operator", {"neq": ["adu_form", "detached"]}),
    ("unknown_operator", {"__import__('os')": ["adu_form", "detached"]}),
    ("invalid_node", {}),
    ("invalid_node", ["eq", "adu_form", "detached"]),
    ("invalid_node", "adu_form == 'detached'"),
    ("invalid_node", None),
    ("multiple_operators", {"eq": ["adu_form", "detached"], "lt": ["floor_area_sqft", 1]}),
    ("invalid_operands", {"eq": ["adu_form"]}),
    ("invalid_operands", {"eq": ["adu_form", "detached", "extra"]}),
    ("invalid_operands", {"eq": "adu_form"}),
    ("invalid_operands", {"all": LEAF}),
    ("invalid_operands", {"not": [LEAF]}),
    ("invalid_operands", {"not": "adu_form"}),
    ("empty_operands", {"all": []}),
    ("empty_operands", {"any": []}),
    ("invalid_fact_reference", {"eq": [5, 5]}),
    ("invalid_fact_reference", {"eq": [{"eq": ["adu_form", "x"]}, "x"]}),
    ("unknown_fact", {"eq": ["lot_size", 5000]}),
    ("type_mismatch", {"eq": ["adu_form", 5]}),
    ("type_mismatch", {"eq": ["existing_dwelling", "yes"]}),
    ("type_mismatch", {"eq": ["existing_dwelling", 1]}),
    ("type_mismatch", {"eq": ["adu_form", None]}),
    ("type_mismatch", {"eq": ["floor_area_sqft", "1200"]}),
    ("type_mismatch", {"in": ["adu_form", ["detached", 5]]}),
    ("non_numeric_comparison", {"lt": ["adu_form", 5]}),
    ("non_numeric_comparison", {"gte": ["existing_dwelling", 1]}),
    ("type_mismatch", {"lt": ["floor_area_sqft", "1200"]}),
    ("invalid_in_list", {"in": ["adu_form", "detached"]}),
    ("empty_in_list", {"in": ["adu_form", []]}),
    ("bool_as_number", {"lt": ["floor_area_sqft", True]}),
    ("bool_as_number", {"eq": ["floor_area_sqft", False]}),
    ("bool_as_number", {"in": ["floor_area_sqft", [500, True]]}),
    ("non_finite_number", {"lt": ["floor_area_sqft", float("nan")]}),
    ("non_finite_number", {"gt": ["floor_area_sqft", float("inf")]}),
    ("max_depth_exceeded", nest_not(MAX_DEPTH + 1)),
    ("max_depth_exceeded", nest_not(5000)),
    ("invalid_operands", {"all": [LEAF, "not-a-node"]}),
]


@pytest.mark.parametrize("code, pred", INVALID_PREDICATES)
def test_validation_errors(code, pred):
    with pytest.raises(PredicateValidationError) as excinfo:
        validate_predicate(pred, S)
    assert excinfo.value.code == code
    assert isinstance(excinfo.value, ValueError)


@pytest.mark.parametrize("code, pred", INVALID_PREDICATES)
def test_evaluate_validates_predicate_first(code, pred):
    with pytest.raises(PredicateValidationError) as excinfo:
        evaluate_predicate(pred, {"adu_form": "detached"}, S)
    assert excinfo.value.code == code


def test_max_depth_boundary_is_allowed():
    validate_predicate(nest_not(MAX_DEPTH), S)
    assert MAX_DEPTH == 20


def test_nested_error_reports_path_without_values():
    # Path convention shared with Person 3's importer: the path names the bad NODE
    # (children as `.all[i]`, `.any[i]`, `.not`), not the operator inside it.
    pred = {"all": [LEAF, {"any": [LEAF, {"lt": ["adu_form", 5]}]}]}
    with pytest.raises(PredicateValidationError) as excinfo:
        validate_predicate(pred, S, "$")
    assert excinfo.value.code == "non_numeric_comparison"
    assert excinfo.value.path == "$.all[1].any[1]"


def test_validate_returns_none_for_valid_predicate():
    assert validate_predicate(DETACHED_SMALL, S) is None


def test_validate_does_not_mutate_input():
    import copy

    pred = copy.deepcopy(DETACHED_SMALL)
    validate_predicate(pred, S)
    evaluate_predicate(pred, {"adu_form": "detached"}, S)
    assert pred == DETACHED_SMALL


# --------------------------------------------------------------------------------------
# Fact validation errors
# --------------------------------------------------------------------------------------

INVALID_FACTS = [
    ("unknown_fact", {"lot_size": 5000}),
    ("unknown_fact", {"__class__": "x"}),
    ("invalid_fact_value", {"adu_form": 5}),
    ("invalid_fact_value", {"existing_dwelling": "true"}),
    ("invalid_fact_value", {"existing_dwelling": 1}),
    ("invalid_fact_value", {"floor_area_sqft": "1200"}),
    ("bool_as_number", {"floor_area_sqft": True}),
    ("non_finite_number", {"floor_area_sqft": float("nan")}),
    ("invalid_facts", ["adu_form", "detached"]),
    ("invalid_facts", None),
    ("invalid_facts", {5: "x"}),
]


@pytest.mark.parametrize("code, facts", INVALID_FACTS)
def test_fact_validation_errors(code, facts):
    with pytest.raises(PredicateValidationError) as excinfo:
        evaluate_predicate(LEAF, facts, S)
    assert excinfo.value.code == code
    with pytest.raises(PredicateValidationError):
        validate_facts(facts, S)


def test_fact_errors_are_raised_even_for_facts_the_predicate_ignores():
    with pytest.raises(PredicateValidationError) as excinfo:
        evaluate_predicate({"eq": ["adu_form", "detached"]}, {"adu_form": "detached", "floor_area_sqft": "big"}, S)
    assert excinfo.value.code == "invalid_fact_value"


SECRET_VALUE = "SECRET-VALUE-123-Main-St"


def test_error_messages_do_not_echo_fact_values():
    bad_fact_cases = [
        {"adu_form": 12345.678},
        {"floor_area_sqft": SECRET_VALUE},
        {"existing_dwelling": SECRET_VALUE},
        {SECRET_VALUE: "x"},
    ]
    for facts in bad_fact_cases:
        with pytest.raises(PredicateValidationError) as excinfo:
            evaluate_predicate(LEAF, facts, S)
        text = str(excinfo.value) + repr(excinfo.value) + excinfo.value.message
        assert SECRET_VALUE not in text
        assert "12345" not in text


def test_error_messages_do_not_echo_literal_values():
    with pytest.raises(PredicateValidationError) as excinfo:
        validate_predicate({"lt": ["floor_area_sqft", SECRET_VALUE]}, S)
    assert SECRET_VALUE not in str(excinfo.value)


# --------------------------------------------------------------------------------------
# Fact schemas
# --------------------------------------------------------------------------------------


def test_default_adu_schema():
    assert dict(ADU_FACT_SCHEMA) == {
        "project_type": FactType.STRING,
        "adu_form": FactType.STRING,
        "existing_dwelling": FactType.BOOLEAN,
        "floor_area_sqft": FactType.NUMBER,
    }
    with pytest.raises(TypeError):
        ADU_FACT_SCHEMA["new_fact"] = FactType.STRING  # type: ignore[index]


def test_custom_schema_from_manifest_strings():
    schema = {"unit_count": "number", "has_alley": "boolean"}
    pred = {"all": [{"gte": ["unit_count", 4]}, {"eq": ["has_alley", True]}]}
    assert evaluate_predicate(pred, {"unit_count": 4, "has_alley": True}, schema).value is Tri.TRUE
    with pytest.raises(PredicateValidationError) as excinfo:
        validate_predicate({"eq": ["adu_form", "detached"]}, schema)
    assert excinfo.value.code == "unknown_fact"


@pytest.mark.parametrize("schema", [{"x": "integer"}, {"x": int}, {"": "string"}, {5: "string"}, None])
def test_invalid_schema_rejected(schema):
    with pytest.raises(PredicateValidationError) as excinfo:
        validate_predicate({"eq": ["x", 1]}, schema)
    assert excinfo.value.code == "invalid_fact_schema"


# --------------------------------------------------------------------------------------
# Input is data, never code
# --------------------------------------------------------------------------------------

INJECTION = "__import__('os').system('echo pwned')"


def test_code_like_strings_are_plain_data(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("eval/exec must never be called")

    monkeypatch.setattr(builtins, "eval", boom)
    monkeypatch.setattr(builtins, "exec", boom)

    pred = {"eq": ["adu_form", INJECTION]}
    assert evaluate_predicate(pred, {"adu_form": INJECTION}, S).value is Tri.TRUE
    assert evaluate_predicate(pred, {"adu_form": "detached"}, S).value is Tri.FALSE
    assert evaluate_predicate({"in": ["adu_form", [INJECTION]]}, {"adu_form": INJECTION}, S).value is Tri.TRUE

    with pytest.raises(PredicateValidationError) as excinfo:
        evaluate_predicate({"eq": [INJECTION, "x"]}, {}, S)
    assert excinfo.value.code == "unknown_fact"


def test_module_source_has_no_dynamic_execution():
    source = Path(predicates.__file__).read_text()
    for banned in ("eval(", "exec(", "compile(", "__import__", "getattr(", "importlib", "subprocess", "os.system"):
        assert banned not in source, banned


# ======================================================================================
# Compatibility with Person 3's importer (origin/p3-platform)
#   - fact schema format {fact: {"type": "bool"|"number"|"enum"|"string", "values": [...]}}
#   - ALLOWED_OPS, PredicateError with .path, validate_predicate(pred, schema, path)
# ======================================================================================

from dataclasses import dataclass as _dataclass
from types import SimpleNamespace

from clearpath.permits.predicates import ALLOWED_OPS, PredicateError

# Exact fact_schema from origin/p3-platform:backend/tests/fixtures/irvine_adu_synthetic/manifest.json
P3_MANIFEST_FACT_SCHEMA = {
    "adu_form": {"type": "enum", "values": ["detached", "attached", "conversion", "jadu"]},
    "existing_dwelling": {"type": "bool"},
    "floor_area_sqft": {"type": "number"},
}
# The applies_if predicates in that same manifest (500 is a synthetic test value there too).
P3_MANIFEST_PREDICATES = [
    ("pathways[0]", {"eq": ["adu_form", "detached"]}),
    ("requirements[0]", {"eq": ["adu_form", "detached"]}),
    ("requirements[1]", {"gt": ["floor_area_sqft", 500]}),
    ("requirements[2]", {"eq": ["existing_dwelling", True]}),
]


@_dataclass(frozen=True)
class FakeFactSpec:
    """Stands in for Person 3's Pydantic FactSpec: an object with .type and .values."""

    type: str
    values: list | None = None


P3_FACTS_AS_OBJECTS = {k: FakeFactSpec(v["type"], v.get("values")) for k, v in P3_MANIFEST_FACT_SCHEMA.items()}

# Person 3's own test schema (origin/p3-platform:backend/tests/unit/test_predicates.py)
P3_TEST_FACTS = {
    "flag": {"type": "bool"},
    "size": {"type": "number"},
    "form": {"type": "enum", "values": ["detached", "attached"]},
    "name": {"type": "string"},
}


def test_allowed_ops_exported_and_frozen():
    assert ALLOWED_OPS == frozenset({"all", "any", "not", "eq", "in", "lt", "lte", "gt", "gte"})
    assert isinstance(ALLOWED_OPS, frozenset)


def test_predicate_error_hierarchy():
    assert issubclass(PredicateValidationError, PredicateError)
    assert issubclass(PredicateError, ValueError)
    with pytest.raises(PredicateError) as excinfo:
        validate_predicate({"all": []}, S)
    assert excinfo.value.path == "applies_if"
    assert excinfo.value.code == "empty_operands"


def test_default_path_prefix_is_applies_if():
    with pytest.raises(PredicateError) as excinfo:
        validate_predicate({"all": [LEAF, {"not": {"eq": ["adu_form", 5]}}]}, S)
    assert excinfo.value.path == "applies_if.all[1].not"


@pytest.mark.parametrize("schema", [P3_MANIFEST_FACT_SCHEMA, P3_FACTS_AS_OBJECTS], ids=["dicts", "objects"])
@pytest.mark.parametrize("owner_path, pred", P3_MANIFEST_PREDICATES)
def test_p3_manifest_predicates_validate(schema, owner_path, pred):
    assert validate_predicate(pred, schema, f"{owner_path}.applies_if") is None


@pytest.mark.parametrize("schema", [P3_MANIFEST_FACT_SCHEMA, P3_FACTS_AS_OBJECTS], ids=["dicts", "objects"])
def test_p3_schema_evaluates_and_validates_facts(schema):
    rule = {"all": [{"eq": ["adu_form", "detached"]}, {"gt": ["floor_area_sqft", 500]}]}
    facts = {"adu_form": "detached", "existing_dwelling": True}
    result = evaluate_predicate(rule, facts, schema)
    assert result == PredicateResult(Tri.UNKNOWN, ("floor_area_sqft",))
    assert to_status(result) == "needs_information"
    assert evaluate_predicate(rule, {**facts, "floor_area_sqft": 600}, schema).value is Tri.TRUE
    assert to_status(evaluate_predicate(rule, {"adu_form": "attached"}, schema)) == "not_applicable"
    assert validate_facts(facts, schema) is None


def test_p3_validator_call_pattern():
    """Mirror of ingestion/validation.py: validate_predicate(owner.applies_if, schema, f'{path}.applies_if')."""
    owners = [
        SimpleNamespace(applies_if={"eq": ["adu_form", "detached"]}),
        SimpleNamespace(applies_if={"all": [{"eq": ["existing_dwelling", 1]}]}),
        SimpleNamespace(applies_if={"all": []}),
        SimpleNamespace(applies_if={"lt": ["adu_form", "detached"]}),
    ]
    issues = []
    for i, owner in enumerate(owners):
        path = f"requirements[{i}]"
        try:
            validate_predicate(owner.applies_if, P3_FACTS_AS_OBJECTS, f"{path}.applies_if")
        except PredicateError as error:
            issues.append(("invalid_predicate", error.path))
    assert issues == [
        ("invalid_predicate", "requirements[1].applies_if.all[0]"),
        ("invalid_predicate", "requirements[2].applies_if"),
        ("invalid_predicate", "requirements[3].applies_if"),
    ]


# Ported from Person 3's test_predicates.py so their expectations keep passing.
@pytest.mark.parametrize(
    "pred",
    [
        {"eq": ["flag", True]},
        {"gt": ["size", 500]},
        {"lte": ["size", 1.5]},
        {"in": ["form", ["detached", "attached"]]},
        {"eq": ["name", "sample"]},
        {"all": [{"eq": ["flag", False]}, {"not": {"any": [{"lt": ["size", 0]}]}}]},
    ],
)
def test_p3_valid_predicates(pred):
    assert validate_predicate(pred, P3_TEST_FACTS) is None


@pytest.mark.parametrize(
    "pred",
    [
        {}, [], {"unknown": []}, {"eq": ["flag", True], "not": {}},
        {"all": []}, {"any": []}, {"not": []}, {"eq": ["flag"]},
        {"eq": ["unknown", True]}, {"eq": [[], True]}, {"eq": ["flag", 1]},
        {"eq": ["size", True]}, {"eq": ["size", "500"]}, {"eq": ["name", 1]},
        {"eq": ["form", "conversion"]}, {"lt": ["form", "detached"]},
        {"gte": ["flag", True]}, {"in": ["size", []]}, {"in": ["size", 1]},
        {"in": ["size", [1, False]]}, {"all": "bad"},
    ],
)
def test_p3_invalid_predicates(pred):
    with pytest.raises(PredicateError) as caught:
        validate_predicate(pred, P3_TEST_FACTS)
    assert caught.value.path.startswith("applies_if")


def test_p3_nested_path_and_no_value_leak():
    with pytest.raises(PredicateError) as caught:
        validate_predicate(
            {"all": [{"eq": ["flag", "FAKE_SECRET_SENTINEL"]}]}, P3_TEST_FACTS, "requirements[2].applies_if"
        )
    assert caught.value.path == "requirements[2].applies_if.all[0]"
    assert "FAKE_SECRET_SENTINEL" not in str(caught.value)
    assert "FAKE_SECRET_SENTINEL" not in repr(caught.value)


# ---- enum facts ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "code, pred",
    [
        ("enum_value_not_allowed", {"eq": ["adu_form", "treehouse"]}),
        ("enum_value_not_allowed", {"in": ["adu_form", ["detached", "treehouse"]]}),
        ("type_mismatch", {"eq": ["adu_form", 5]}),
        ("type_mismatch", {"in": ["adu_form", ["detached", None]]}),
        ("non_numeric_comparison", {"lt": ["adu_form", "detached"]}),
        ("non_numeric_comparison", {"gte": ["adu_form", 1]}),
    ],
)
def test_enum_predicate_errors(code, pred):
    with pytest.raises(PredicateValidationError) as excinfo:
        validate_predicate(pred, P3_MANIFEST_FACT_SCHEMA)
    assert excinfo.value.code == code


def test_enum_in_list_with_allowed_values():
    pred = {"in": ["adu_form", ["attached", "jadu"]]}
    assert evaluate_predicate(pred, {"adu_form": "jadu"}, P3_MANIFEST_FACT_SCHEMA).value is Tri.TRUE
    assert evaluate_predicate(pred, {"adu_form": "detached"}, P3_MANIFEST_FACT_SCHEMA).value is Tri.FALSE
    assert evaluate_predicate(pred, {}, P3_MANIFEST_FACT_SCHEMA).value is Tri.UNKNOWN


@pytest.mark.parametrize(
    "code, facts",
    [
        ("enum_value_not_allowed", {"adu_form": SECRET_VALUE}),
        ("invalid_fact_value", {"adu_form": 5}),
        ("invalid_fact_value", {"existing_dwelling": 1}),
        ("bool_as_number", {"floor_area_sqft": True}),
    ],
)
def test_enum_and_bool_fact_errors(code, facts):
    with pytest.raises(PredicateValidationError) as excinfo:
        validate_facts(facts, P3_MANIFEST_FACT_SCHEMA)
    assert excinfo.value.code == code
    assert SECRET_VALUE not in str(excinfo.value)


def test_bool_alias_equals_boolean():
    for kind in ("bool", "boolean", FactType.BOOLEAN, {"type": "bool"}, FakeFactSpec("bool")):
        schema = {"flag": kind}
        assert evaluate_predicate({"eq": ["flag", True]}, {"flag": True}, schema).value is Tri.TRUE


def test_mixed_schema_formats_in_one_schema():
    schema = {"a": "boolean", "b": {"type": "number"}, "c": FakeFactSpec("enum", ["x", "y"]), "d": FactType.STRING}
    pred = {"all": [{"eq": ["a", True]}, {"gte": ["b", 1]}, {"in": ["c", ["x"]]}, {"eq": ["d", "z"]}]}
    assert evaluate_predicate(pred, {"a": True, "b": 2, "c": "x", "d": "z"}, schema).value is Tri.TRUE


@pytest.mark.parametrize(
    "spec",
    [
        {"type": "enum"},
        {"type": "enum", "values": []},
        {"type": "enum", "values": "detached"},
        {"type": "enum", "values": ["detached", 5]},
        {"type": "bool", "values": ["x"]},
        {"type": "integer"},
        {"values": ["x"]},
        {"type": "number", "extra": 1},
        "enum",
        FakeFactSpec("enum", None),
        FakeFactSpec("number", ["x"]),
        FakeFactSpec("float"),
        object(),
    ],
)
def test_invalid_new_format_schemas(spec):
    with pytest.raises(PredicateValidationError) as excinfo:
        validate_predicate({"eq": ["x", True]}, {"x": spec})
    assert excinfo.value.code == "invalid_fact_schema"
