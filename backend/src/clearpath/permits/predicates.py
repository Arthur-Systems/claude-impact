"""Validate the data-only predicate grammar; never execute expressions."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clearpath.ingestion.schemas import FactSpec

ALLOWED_OPS = frozenset({'all', 'any', 'not', 'eq', 'in', 'lt', 'lte', 'gt', 'gte'})


class PredicateError(ValueError):
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"invalid_predicate: {path}")


def validate_predicate(
    pred: object, fact_schema: Mapping[str, FactSpec | dict], path: str = 'applies_if'
) -> None:
    if not isinstance(pred, dict) or len(pred) != 1:
        raise PredicateError(path)
    op, args = next(iter(pred.items()))
    if op not in ALLOWED_OPS:
        raise PredicateError(path)
    if op in {'all', 'any'}:
        if not isinstance(args, list) or not args:
            raise PredicateError(path)
        for i, child in enumerate(args):
            validate_predicate(child, fact_schema, f'{path}.{op}[{i}]')
        return
    if op == 'not':
        validate_predicate(args, fact_schema, f'{path}.not')
        return
    if not isinstance(args, list) or len(args) != 2:
        raise PredicateError(path)
    fact, literal = args
    if not isinstance(fact, str) or fact not in fact_schema:
        raise PredicateError(path)
    spec = fact_schema[fact]
    kind = spec['type'] if isinstance(spec, dict) else spec.type
    values = spec.get('values') if isinstance(spec, dict) else spec.values
    if op in {'lt', 'lte', 'gt', 'gte'} and kind != 'number':
        raise PredicateError(path)
    literals = literal if op == 'in' else [literal]
    if not isinstance(literals, list) or not literals:
        raise PredicateError(path)
    for value in literals:
        valid = (
            (kind == 'bool' and type(value) is bool)
            or (kind == 'number' and type(value) in (int, float))
            or (kind == 'string' and isinstance(value, str))
            or (kind == 'enum' and isinstance(value, str) and value in (values or []))
        )
        if not valid:
            raise PredicateError(path)


# evaluate_predicate: owned by Person 4 (three-valued logic), not implemented here.
