"""Validate the data-only predicate grammar; never execute expressions."""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from clearpath.ingestion.schemas import FactSpec

ALLOWED_OPS = frozenset({'all', 'any', 'not', 'eq', 'in', 'lt', 'lte', 'gt', 'gte'})
PredicateReason = Literal[
    'unknown_operator', 'multiple_keys', 'not_an_object', 'empty_operands',
    'bad_operand_shape', 'unknown_fact', 'literal_type_mismatch',
    'enum_value_not_allowed', 'comparison_on_non_number', 'non_finite_number',
    'too_deep',
]


class PredicateError(ValueError):
    def __init__(self, path: str, reason: PredicateReason):
        self.path = path
        self.reason = reason
        super().__init__(f"invalid_predicate: {path} ({reason})")


def validate_predicate(
    pred: object, fact_schema: Mapping[str, FactSpec | dict], path: str = 'applies_if'
) -> None:
    """Validate at most 32 nesting levels below the root (depth 0), without recursion."""
    pending: list[tuple[object, str, int]] = [(pred, path, 0)]
    while pending:
        pred, path, depth = pending.pop()
        if depth > 32:
            raise PredicateError(path, 'too_deep')
        if not isinstance(pred, dict):
            raise PredicateError(path, 'not_an_object')
        if len(pred) != 1:
            raise PredicateError(path, 'multiple_keys' if pred else 'bad_operand_shape')
        op, args = next(iter(pred.items()))
        if op not in ALLOWED_OPS:
            raise PredicateError(path, 'unknown_operator')
        # Only allowlisted operator names enter diagnostics, never submitted keys.
        operand_path = f'{path}.{op}'
        if op in {'all', 'any'}:
            if not isinstance(args, list):
                raise PredicateError(operand_path, 'bad_operand_shape')
            if not args:
                raise PredicateError(operand_path, 'empty_operands')
            # LIFO traversal preserves the original left-to-right error order.
            for i in range(len(args) - 1, -1, -1):
                pending.append((args[i], f'{operand_path}[{i}]', depth + 1))
            continue
        if op == 'not':
            pending.append((args, operand_path, depth + 1))
            continue
        if not isinstance(args, list) or len(args) != 2:
            raise PredicateError(operand_path, 'bad_operand_shape')
        fact, literal = args
        if not isinstance(fact, str):
            raise PredicateError(operand_path, 'bad_operand_shape')
        if fact not in fact_schema:
            raise PredicateError(operand_path, 'unknown_fact')
        spec = fact_schema[fact]
        kind = spec['type'] if isinstance(spec, dict) else spec.type
        values = spec.get('values') if isinstance(spec, dict) else spec.values
        if op in {'lt', 'lte', 'gt', 'gte'} and kind != 'number':
            raise PredicateError(operand_path, 'comparison_on_non_number')
        literals = literal if op == 'in' else [literal]
        if not isinstance(literals, list):
            raise PredicateError(operand_path, 'bad_operand_shape')
        if not literals:
            raise PredicateError(operand_path, 'empty_operands')
        for value in literals:
            if type(value) is float and not isfinite(value):
                raise PredicateError(operand_path, 'non_finite_number')
            valid = (
                (kind == 'bool' and type(value) is bool)
                or (kind == 'number' and type(value) in (int, float))
                or (kind in {'string', 'enum'} and isinstance(value, str))
            )
            if not valid:
                raise PredicateError(operand_path, 'literal_type_mismatch')
            if kind == 'enum' and value not in (values or []):
                raise PredicateError(operand_path, 'enum_value_not_allowed')


# evaluate_predicate: owned by Person 4 (three-valued logic), not implemented here.
