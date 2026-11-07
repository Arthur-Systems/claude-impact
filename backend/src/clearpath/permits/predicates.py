"""Three-valued permit-rule predicates for ClearPath (SPEC.md section 7).

A predicate is plain JSON-like data, for example::

    {"all": [{"eq": ["adu_form", "detached"]}, {"lt": ["floor_area_sqft", 1200]}]}

Supported operators: ``all``, ``any``, ``not``, ``eq``, ``in``, ``lt``, ``lte``, ``gt``,
``gte``. The left operand of a comparison is always a fact key from the fact schema; the
right operand is always a literal. Predicates are interpreted by a fixed dispatch over
known operator names. Nothing in the input is ever run as code or turned into a query.

Evaluation has three values. A fact that is absent or ``None`` is UNKNOWN, never false,
so a missing fact can produce ``needs_information`` but never ``not_applicable``.

Error messages name operators, fact keys, paths and type names. They never include a
fact value or a literal value. Persons 3 (importer) and 5 (projects) may import
``validate_predicate`` and ``validate_facts``; this module has no side effects and uses
only the standard library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

__all__ = [
    "ADU_FACT_SCHEMA",
    "MAX_DEPTH",
    "FactType",
    "PredicateResult",
    "PredicateValidationError",
    "Tri",
    "evaluate_predicate",
    "to_status",
    "validate_facts",
    "validate_predicate",
]

MAX_DEPTH = 20
"""Deepest allowed predicate nesting. The root node is level 1."""


class FactType(str, Enum):
    """Type of a rule fact. String values match what a manifest's fact schema uses."""

    STRING = "string"
    BOOLEAN = "boolean"
    NUMBER = "number"


ADU_FACT_SCHEMA: Mapping[str, FactType] = MappingProxyType(
    {
        "project_type": FactType.STRING,
        "adu_form": FactType.STRING,
        "existing_dwelling": FactType.BOOLEAN,
        "floor_area_sqft": FactType.NUMBER,
    }
)
"""Fact schema for the first ADU profile (team-roles.md, Contract 1). Read-only."""


class Tri(Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PredicateResult:
    value: Tri
    missing_keys: tuple[str, ...] = ()
    """Sorted fact keys whose absence keeps the result UNKNOWN. Empty when decided."""


class PredicateValidationError(ValueError):
    """A predicate, fact set or fact schema is malformed.

    ``code`` is a short machine-readable reason. ``path`` locates the bad node, e.g.
    ``$.all[1].lt``. Neither the message nor the path contains user-supplied values.
    """

    def __init__(self, code: str, message: str, path: str = "$") -> None:
        super().__init__(f"{code}: {message} (at {path})")
        self.code = code
        self.message = message
        self.path = path

    def __repr__(self) -> str:
        return f"PredicateValidationError(code={self.code!r}, path={self.path!r})"


_BOOLEAN_OPS = ("all", "any")
_COMPARISON_OPS = ("eq", "in", "lt", "lte", "gt", "gte")
_ORDERING_OPS = ("lt", "lte", "gt", "gte")
_OPERATORS = frozenset(_BOOLEAN_OPS + ("not",) + _COMPARISON_OPS)

_STATUS = {
    Tri.TRUE: "applies",
    Tri.FALSE: "not_applicable",
    Tri.UNKNOWN: "needs_information",
}


# --------------------------------------------------------------------------------------
# Schema and value type checks
# --------------------------------------------------------------------------------------


def _normalize_schema(fact_schema: Any) -> dict[str, FactType]:
    if not isinstance(fact_schema, Mapping):
        raise PredicateValidationError("invalid_fact_schema", "fact schema must be a mapping")
    normalized: dict[str, FactType] = {}
    for key, kind in fact_schema.items():
        if not isinstance(key, str) or not key:
            raise PredicateValidationError("invalid_fact_schema", "fact keys must be non-empty strings")
        if isinstance(kind, FactType):
            normalized[key] = kind
            continue
        if not isinstance(kind, str) or kind not in {t.value for t in FactType}:
            raise PredicateValidationError(
                "invalid_fact_schema",
                f"fact {key!r} must have type 'string', 'boolean' or 'number'",
            )
        normalized[key] = FactType(kind)
    return normalized


def _type_name(value: Any) -> str:
    return type(value).__name__


def _check_value(value: Any, kind: FactType, *, bad_type_code: str, what: str, path: str) -> None:
    """Raise unless ``value`` (never None here) matches ``kind``. Messages omit the value."""
    if kind is FactType.NUMBER:
        if isinstance(value, bool):
            raise PredicateValidationError("bool_as_number", f"{what} must be a number, not a boolean", path)
        if not isinstance(value, (int, float)):
            raise PredicateValidationError(bad_type_code, f"{what} must be a number, got {_type_name(value)}", path)
        if isinstance(value, float) and not math.isfinite(value):
            raise PredicateValidationError("non_finite_number", f"{what} must be a finite number", path)
    elif kind is FactType.BOOLEAN:
        if not isinstance(value, bool):
            raise PredicateValidationError(bad_type_code, f"{what} must be a boolean, got {_type_name(value)}", path)
    elif kind is FactType.STRING:
        if not isinstance(value, str):
            raise PredicateValidationError(bad_type_code, f"{what} must be a string, got {_type_name(value)}", path)


# --------------------------------------------------------------------------------------
# Predicate validation
# --------------------------------------------------------------------------------------


def _operator_of(node: Any, path: str) -> tuple[str, Any]:
    if not isinstance(node, dict) or not node:
        raise PredicateValidationError("invalid_node", "each predicate node must be an object with one operator", path)
    if len(node) != 1:
        raise PredicateValidationError("multiple_operators", "a predicate node must have exactly one operator", path)
    ((op, operand),) = node.items()
    if not isinstance(op, str) or op not in _OPERATORS:
        raise PredicateValidationError("unknown_operator", "unsupported operator", path)
    return op, operand


def _validate_node(node: Any, schema: dict[str, FactType], path: str, depth: int) -> None:
    if depth > MAX_DEPTH:
        raise PredicateValidationError("max_depth_exceeded", f"predicate nesting exceeds {MAX_DEPTH} levels", path)
    op, operand = _operator_of(node, path)
    here = f"{path}.{op}"

    if op in _BOOLEAN_OPS:
        if not isinstance(operand, list):
            raise PredicateValidationError("invalid_operands", f"'{op}' takes a list of predicates", here)
        if not operand:
            raise PredicateValidationError("empty_operands", f"'{op}' needs at least one predicate", here)
        for index, child in enumerate(operand):
            child_path = f"{here}[{index}]"
            if not isinstance(child, dict):
                raise PredicateValidationError("invalid_operands", f"'{op}' items must be predicate objects", child_path)
            _validate_node(child, schema, child_path, depth + 1)
        return

    if op == "not":
        if not isinstance(operand, dict):
            raise PredicateValidationError("invalid_operands", "'not' takes a single predicate object", here)
        _validate_node(operand, schema, here, depth + 1)
        return

    # Comparison: [fact_key, literal]
    if not isinstance(operand, list) or len(operand) != 2:
        raise PredicateValidationError("invalid_operands", f"'{op}' takes [fact_key, value]", here)
    key, literal = operand
    if not isinstance(key, str):
        raise PredicateValidationError("invalid_fact_reference", f"'{op}' left operand must be a fact key string", here)
    if key not in schema:
        raise PredicateValidationError("unknown_fact", "fact key is not declared in the fact schema", here)
    kind = schema[key]
    what = f"'{op}' value for fact {key!r}"

    if op in _ORDERING_OPS:
        if kind is not FactType.NUMBER:
            raise PredicateValidationError(
                "non_numeric_comparison", f"'{op}' needs a number fact; {key!r} is {kind.value}", here
            )
        _check_value(literal, kind, bad_type_code="type_mismatch", what=what, path=here)
    elif op == "in":
        if not isinstance(literal, list):
            raise PredicateValidationError("invalid_in_list", "'in' right operand must be a list", here)
        if not literal:
            raise PredicateValidationError("empty_in_list", "'in' list must not be empty", here)
        for index, item in enumerate(literal):
            if item is None:
                raise PredicateValidationError("type_mismatch", f"{what} must not be null", f"{here}[{index}]")
            _check_value(item, kind, bad_type_code="type_mismatch", what=what, path=f"{here}[{index}]")
    else:  # eq
        if literal is None:
            raise PredicateValidationError("type_mismatch", f"{what} must not be null", here)
        _check_value(literal, kind, bad_type_code="type_mismatch", what=what, path=here)


def validate_predicate(predicate: Any, fact_schema: Mapping[str, Any]) -> None:
    """Raise PredicateValidationError if ``predicate`` is not valid for ``fact_schema``."""
    schema = _normalize_schema(fact_schema)
    _validate_node(predicate, schema, "$", 1)


# --------------------------------------------------------------------------------------
# Fact validation
# --------------------------------------------------------------------------------------


def _validate_facts(facts: Any, schema: dict[str, FactType]) -> None:
    if not isinstance(facts, Mapping):
        raise PredicateValidationError("invalid_facts", "facts must be an object of fact_key: value", "facts")
    for key, value in facts.items():
        if not isinstance(key, str):
            raise PredicateValidationError("invalid_facts", "fact keys must be strings", "facts")
        if key not in schema:
            raise PredicateValidationError("unknown_fact", "facts include a key not declared in the fact schema", "facts")
        if value is None:
            continue
        _check_value(value, schema[key], bad_type_code="invalid_fact_value", what=f"fact {key!r}", path=f"facts.{key}")


def validate_facts(facts: Any, fact_schema: Mapping[str, Any]) -> None:
    """Raise PredicateValidationError if ``facts`` has unknown keys or wrongly typed values.

    Absent keys and ``None`` values are allowed: they mean "unknown".
    """
    _validate_facts(facts, _normalize_schema(fact_schema))


# --------------------------------------------------------------------------------------
# Evaluation (input already validated)
# --------------------------------------------------------------------------------------


def _compare(op: str, value: Any, literal: Any) -> bool:
    if op == "eq":
        return value == literal
    if op == "in":
        return any(value == item for item in literal)
    if op == "lt":
        return value < literal
    if op == "lte":
        return value <= literal
    if op == "gt":
        return value > literal
    if op == "gte":
        return value >= literal
    raise AssertionError("unreachable: operator was validated")


def _evaluate_node(node: dict, facts: Mapping[str, Any]) -> tuple[Tri, frozenset[str]]:
    ((op, operand),) = node.items()

    if op == "not":
        value, missing = _evaluate_node(operand, facts)
        if value is Tri.TRUE:
            return Tri.FALSE, frozenset()
        if value is Tri.FALSE:
            return Tri.TRUE, frozenset()
        return Tri.UNKNOWN, missing

    if op in _BOOLEAN_OPS:
        decisive = Tri.FALSE if op == "all" else Tri.TRUE
        otherwise = Tri.TRUE if op == "all" else Tri.FALSE
        unknown_missing: set[str] = set()
        saw_unknown = False
        for child in operand:
            value, missing = _evaluate_node(child, facts)
            if value is decisive:
                return decisive, frozenset()
            if value is Tri.UNKNOWN:
                saw_unknown = True
                unknown_missing |= missing
        if saw_unknown:
            return Tri.UNKNOWN, frozenset(unknown_missing)
        return otherwise, frozenset()

    key, literal = operand
    value = facts.get(key)
    if value is None:
        return Tri.UNKNOWN, frozenset((key,))
    return (Tri.TRUE if _compare(op, value, literal) else Tri.FALSE), frozenset()


def evaluate_predicate(
    predicate: Any, facts: Mapping[str, Any], fact_schema: Mapping[str, Any]
) -> PredicateResult:
    """Evaluate ``predicate`` against ``facts`` with true/false/unknown logic.

    Validates the schema, the predicate and the facts first, raising
    PredicateValidationError on any problem. Absent or ``None`` facts are UNKNOWN.
    """
    schema = _normalize_schema(fact_schema)
    _validate_node(predicate, schema, "$", 1)
    _validate_facts(facts, schema)
    value, missing = _evaluate_node(predicate, facts)
    if value is not Tri.UNKNOWN:
        missing = frozenset()
    return PredicateResult(value=value, missing_keys=tuple(sorted(missing)))


def to_status(result: PredicateResult) -> str:
    """Map a result to ``applies`` / ``not_applicable`` / ``needs_information``."""
    return _STATUS[result.value]
