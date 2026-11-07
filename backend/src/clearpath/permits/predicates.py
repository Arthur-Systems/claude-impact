"""Three-valued permit-rule predicates for ClearPath (SPEC.md section 7).

A predicate is plain JSON-like data, for example::

    {"all": [{"eq": ["adu_form", "detached"]}, {"lt": ["floor_area_sqft", 1200]}]}

Supported operators (``ALLOWED_OPS``): ``all``, ``any``, ``not``, ``eq``, ``in``, ``lt``,
``lte``, ``gt``, ``gte``. The left operand of a comparison is always a fact key from the
fact schema; the right operand is always a literal. Predicates are interpreted by a fixed
dispatch over known operator names. Nothing in the input is ever run as code or turned
into a query.

Evaluation has three values. A fact that is absent or ``None`` is UNKNOWN, never false,
so a missing fact can produce ``needs_information`` but never ``not_applicable``.

Fact schemas may be written in any of these forms, mixed freely:

* ``{"floor_area_sqft": "number"}`` or ``FactType.NUMBER``; types ``string``,
  ``boolean`` (alias ``bool``) and ``number``
* the manifest form ``{"adu_form": {"type": "enum", "values": ["detached", ...]}}`` with
  types ``bool``, ``number``, ``string`` or ``enum``
* objects with ``.type`` and ``.values`` attributes, such as the importer's Pydantic
  ``FactSpec``

Error paths follow the importer's convention: they name the bad node, e.g.
``requirements[2].applies_if.all[0]``. Error messages and paths contain operators, fact
keys, indexes and type names, never a fact value or a literal value. This module is a
drop-in replacement for the importer's validator: ``except PredicateError`` catches every
error raised here. It has no side effects and uses only the standard library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

__all__ = [
    "ADU_FACT_SCHEMA",
    "ALLOWED_OPS",
    "MAX_DEPTH",
    "FactType",
    "PredicateError",
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

DEFAULT_PATH = "applies_if"

ALLOWED_OPS = frozenset({"all", "any", "not", "eq", "in", "lt", "lte", "gt", "gte"})


class FactType(str, Enum):
    """Type of a rule fact."""

    STRING = "string"
    BOOLEAN = "boolean"
    NUMBER = "number"
    ENUM = "enum"


_TYPE_NAMES = {
    "string": FactType.STRING,
    "boolean": FactType.BOOLEAN,
    "bool": FactType.BOOLEAN,
    "number": FactType.NUMBER,
    "enum": FactType.ENUM,
}


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


class PredicateError(ValueError):
    """Base error for an invalid predicate, fact set or fact schema.

    ``path`` locates the bad node (e.g. ``requirements[2].applies_if.all[0]``), ``code``
    is a short machine-readable reason. Neither contains user-supplied values.
    """

    def __init__(self, path: str = DEFAULT_PATH, code: str = "invalid_predicate", message: str = "invalid predicate"):
        super().__init__(f"{code}: {message} (at {path})")
        self.path = path
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, path={self.path!r})"


class PredicateValidationError(PredicateError):
    """The error raised by this module. Signature: ``(code, message, path)``."""

    def __init__(self, code: str, message: str, path: str = DEFAULT_PATH) -> None:
        super().__init__(path=path, code=code, message=message)


_BOOLEAN_OPS = ("all", "any")
_ORDERING_OPS = ("lt", "lte", "gt", "gte")

_STATUS = {
    Tri.TRUE: "applies",
    Tri.FALSE: "not_applicable",
    Tri.UNKNOWN: "needs_information",
}


# --------------------------------------------------------------------------------------
# Fact schema normalization
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Spec:
    kind: FactType
    values: frozenset[str] | None = None


def _schema_error(message: str) -> PredicateValidationError:
    return PredicateValidationError("invalid_fact_schema", message, "fact_schema")


def _spec_parts(key: str, spec: Any) -> tuple[Any, Any]:
    """Return (type, values) from a type name, a mapping, or a FactSpec-like object."""
    if isinstance(spec, str):  # includes FactType
        return spec, None
    if isinstance(spec, Mapping):
        if "type" not in spec or not set(spec) <= {"type", "values"}:
            raise _schema_error(f"fact {key!r} needs 'type' and only 'type'/'values'")
        return spec["type"], spec.get("values")
    try:
        return spec.type, spec.values
    except AttributeError:
        raise _schema_error(f"fact {key!r} has an unsupported spec") from None


def _normalize_spec(key: str, spec: Any) -> _Spec:
    raw_type, values = _spec_parts(key, spec)
    kind = raw_type if isinstance(raw_type, FactType) else _TYPE_NAMES.get(raw_type) if isinstance(raw_type, str) else None
    if kind is None:
        raise _schema_error(f"fact {key!r} must have type 'string', 'bool', 'number' or 'enum'")
    if kind is FactType.ENUM:
        if (
            not isinstance(values, (list, tuple))
            or not values
            or not all(isinstance(v, str) for v in values)
        ):
            raise _schema_error(f"enum fact {key!r} needs a non-empty list of string values")
        return _Spec(kind, frozenset(values))
    if values is not None:
        raise _schema_error(f"fact {key!r}: values are only allowed for enum facts")
    return _Spec(kind)


def _normalize_schema(fact_schema: Any) -> dict[str, _Spec]:
    if not isinstance(fact_schema, Mapping):
        raise _schema_error("fact schema must be a mapping")
    normalized: dict[str, _Spec] = {}
    for key, spec in fact_schema.items():
        if not isinstance(key, str) or not key:
            raise _schema_error("fact keys must be non-empty strings")
        normalized[key] = _normalize_spec(key, spec)
    return normalized


# --------------------------------------------------------------------------------------
# Value type checks
# --------------------------------------------------------------------------------------


def _type_name(value: Any) -> str:
    return type(value).__name__


def _check_value(value: Any, spec: _Spec, *, bad_type_code: str, what: str, path: str) -> None:
    """Raise unless ``value`` (never None here) matches ``spec``. Messages omit the value."""
    kind = spec.kind
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
    else:  # STRING or ENUM
        if not isinstance(value, str):
            raise PredicateValidationError(bad_type_code, f"{what} must be a string, got {_type_name(value)}", path)
        if kind is FactType.ENUM and value not in spec.values:
            raise PredicateValidationError("enum_value_not_allowed", f"{what} is not one of the allowed values", path)


# --------------------------------------------------------------------------------------
# Predicate validation
# --------------------------------------------------------------------------------------


def _operator_of(node: Any, path: str) -> tuple[str, Any]:
    if not isinstance(node, dict) or not node:
        raise PredicateValidationError("invalid_node", "each predicate node must be an object with one operator", path)
    if len(node) != 1:
        raise PredicateValidationError("multiple_operators", "a predicate node must have exactly one operator", path)
    ((op, operand),) = node.items()
    if not isinstance(op, str) or op not in ALLOWED_OPS:
        raise PredicateValidationError("unknown_operator", "unsupported operator", path)
    return op, operand


def _validate_node(node: Any, schema: dict[str, _Spec], path: str, depth: int) -> None:
    if depth > MAX_DEPTH:
        raise PredicateValidationError("max_depth_exceeded", f"predicate nesting exceeds {MAX_DEPTH} levels", path)
    op, operand = _operator_of(node, path)

    if op in _BOOLEAN_OPS:
        if not isinstance(operand, list):
            raise PredicateValidationError("invalid_operands", f"'{op}' takes a list of predicates", path)
        if not operand:
            raise PredicateValidationError("empty_operands", f"'{op}' needs at least one predicate", path)
        for index, child in enumerate(operand):
            child_path = f"{path}.{op}[{index}]"
            if not isinstance(child, dict):
                raise PredicateValidationError("invalid_operands", f"'{op}' items must be predicate objects", child_path)
            _validate_node(child, schema, child_path, depth + 1)
        return

    if op == "not":
        if not isinstance(operand, dict):
            raise PredicateValidationError("invalid_operands", "'not' takes a single predicate object", path)
        _validate_node(operand, schema, f"{path}.not", depth + 1)
        return

    # Comparison: [fact_key, literal]
    if not isinstance(operand, list) or len(operand) != 2:
        raise PredicateValidationError("invalid_operands", f"'{op}' takes [fact_key, value]", path)
    key, literal = operand
    if not isinstance(key, str):
        raise PredicateValidationError("invalid_fact_reference", f"'{op}' left operand must be a fact key string", path)
    if key not in schema:
        raise PredicateValidationError("unknown_fact", "fact key is not declared in the fact schema", path)
    spec = schema[key]
    what = f"'{op}' value for fact {key!r}"

    if op in _ORDERING_OPS:
        if spec.kind is not FactType.NUMBER:
            raise PredicateValidationError(
                "non_numeric_comparison", f"'{op}' needs a number fact; {key!r} is {spec.kind.value}", path
            )
        _check_value(literal, spec, bad_type_code="type_mismatch", what=what, path=path)
    elif op == "in":
        if not isinstance(literal, list):
            raise PredicateValidationError("invalid_in_list", "'in' right operand must be a list", path)
        if not literal:
            raise PredicateValidationError("empty_in_list", "'in' list must not be empty", path)
        for item in literal:
            if item is None:
                raise PredicateValidationError("type_mismatch", f"{what} must not be null", path)
            _check_value(item, spec, bad_type_code="type_mismatch", what=what, path=path)
    else:  # eq
        if literal is None:
            raise PredicateValidationError("type_mismatch", f"{what} must not be null", path)
        _check_value(literal, spec, bad_type_code="type_mismatch", what=what, path=path)


def validate_predicate(predicate: Any, fact_schema: Mapping[str, Any], path: str = DEFAULT_PATH) -> None:
    """Raise PredicateValidationError if ``predicate`` is not valid for ``fact_schema``.

    ``path`` prefixes error paths, e.g. ``f"requirements[{i}].applies_if"``.
    """
    schema = _normalize_schema(fact_schema)
    _validate_node(predicate, schema, path, 1)


# --------------------------------------------------------------------------------------
# Fact validation
# --------------------------------------------------------------------------------------


def _validate_facts(facts: Any, schema: dict[str, _Spec]) -> None:
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
    predicate: Any, facts: Mapping[str, Any], fact_schema: Mapping[str, Any], path: str = DEFAULT_PATH
) -> PredicateResult:
    """Evaluate ``predicate`` against ``facts`` with true/false/unknown logic.

    Validates the schema, the predicate and the facts first, raising
    PredicateValidationError on any problem. Absent or ``None`` facts are UNKNOWN.
    """
    schema = _normalize_schema(fact_schema)
    _validate_node(predicate, schema, path, 1)
    _validate_facts(facts, schema)
    value, missing = _evaluate_node(predicate, facts)
    if value is not Tri.UNKNOWN:
        missing = frozenset()
    return PredicateResult(value=value, missing_keys=tuple(sorted(missing)))


def to_status(result: PredicateResult) -> str:
    """Map a result to ``applies`` / ``not_applicable`` / ``needs_information``."""
    return _STATUS[result.value]
