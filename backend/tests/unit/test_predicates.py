import pytest

from clearpath.permits.predicates import ALLOWED_OPS, PredicateError, validate_predicate


FACTS = {
    'flag': {'type': 'bool'}, 'size': {'type': 'number'},
    'form': {'type': 'enum', 'values': ['detached', 'attached']},
    'name': {'type': 'string'},
}


@pytest.mark.parametrize('pred', [
    {'eq': ['flag', True]}, {'gt': ['size', 500]}, {'lte': ['size', 1.5]},
    {'in': ['form', ['detached', 'attached']]}, {'eq': ['name', 'sample']},
    {'all': [{'eq': ['flag', False]}, {'not': {'any': [{'lt': ['size', 0]}]}}]},
])
def test_valid_predicates(pred):
    assert validate_predicate(pred, FACTS) is None


@pytest.mark.parametrize(('pred', 'suffix', 'reason'), [
    ({}, '', 'bad_operand_shape'),
    ([], '', 'not_an_object'),
    ({'SENTINEL\nX': []}, '', 'unknown_operator'),
    ({'eq': ['flag', True], 'not': {}}, '', 'multiple_keys'),
    ({'all': []}, '.all', 'empty_operands'),
    ({'any': []}, '.any', 'empty_operands'),
    ({'not': []}, '.not', 'not_an_object'),
    ({'eq': ['flag']}, '.eq', 'bad_operand_shape'),
    ({'eq': 'SENTINEL\nX'}, '.eq', 'bad_operand_shape'),
    ({'eq': ['SENTINEL\nX', True]}, '.eq', 'unknown_fact'),
    ({'eq': [[], True]}, '.eq', 'bad_operand_shape'),
    ({'eq': ['flag', 1]}, '.eq', 'literal_type_mismatch'),
    ({'eq': ['size', True]}, '.eq', 'literal_type_mismatch'),
    ({'eq': ['size', '500']}, '.eq', 'literal_type_mismatch'),
    ({'eq': ['name', 1]}, '.eq', 'literal_type_mismatch'),
    ({'eq': ['form', 1]}, '.eq', 'literal_type_mismatch'),
    ({'eq': ['form', 'SENTINEL\nX']}, '.eq', 'enum_value_not_allowed'),
    ({'lt': ['form', 'detached']}, '.lt', 'comparison_on_non_number'),
    ({'gte': ['flag', True]}, '.gte', 'comparison_on_non_number'),
    ({'in': ['size', []]}, '.in', 'empty_operands'),
    ({'in': ['size', 1]}, '.in', 'bad_operand_shape'),
    ({'in': ['size', [1, False]]}, '.in', 'literal_type_mismatch'),
    ({'in': ['form', ['detached', 'SENTINEL\nX']]}, '.in', 'enum_value_not_allowed'),
    ({'all': 'bad'}, '.all', 'bad_operand_shape'),
    ({'any': {}}, '.any', 'bad_operand_shape'),
])
def test_invalid_predicates(pred, suffix, reason):
    with pytest.raises(PredicateError) as caught:
        validate_predicate(pred, FACTS)
    assert caught.value.path == f'applies_if{suffix}'
    assert caught.value.reason == reason
    assert str(caught.value) == f'invalid_predicate: applies_if{suffix} ({reason})'
    assert 'SENTINEL' not in str(caught.value)
    assert '\n' not in str(caught.value)


def test_nested_path_and_no_value_leak():
    with pytest.raises(PredicateError) as caught:
        validate_predicate({'all': [{'eq': ['flag', 'FAKE_SECRET_SENTINEL']}]}, FACTS,
                           'requirements[2].applies_if')
    assert caught.value.path == 'requirements[2].applies_if.all[0].eq'
    assert caught.value.reason == 'literal_type_mismatch'
    assert 'FAKE_SECRET_SENTINEL' not in str(caught.value)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')], ids=['nan', 'inf', '-inf'])
@pytest.mark.parametrize('op', ['eq', 'in', 'lt', 'lte', 'gt', 'gte'])
def test_non_finite_predicate_literals_are_rejected(value, op):
    literal = [0, value] if op == 'in' else value
    with pytest.raises(PredicateError) as caught:
        validate_predicate({'all': [{op: ['size', literal]}]}, FACTS)
    assert caught.value.path == f'applies_if.all[0].{op}'
    assert caught.value.reason == 'non_finite_number'
    assert str(caught.value) == f'invalid_predicate: applies_if.all[0].{op} (non_finite_number)'


@pytest.mark.parametrize('value', [0, 1.5, -1e308, 1e308, 10 ** 400])
def test_finite_numbers_and_large_integers_remain_valid(value):
    assert validate_predicate({'eq': ['size', value]}, FACTS) is None


def nested_predicate(op, nesting):
    pred = {'eq': ['flag', True]}
    for _ in range(nesting):
        pred = {op: pred if op == 'not' else [pred]}
    return pred


@pytest.mark.parametrize('op', ['all', 'any', 'not'])
def test_predicate_nesting_at_depth_limit_is_valid(op):
    assert validate_predicate(nested_predicate(op, 32), FACTS) is None


@pytest.mark.parametrize('op', ['all', 'any', 'not'])
@pytest.mark.parametrize('nesting', [33, 2000])
def test_predicate_nesting_over_limit_has_bounded_diagnostic(op, nesting):
    with pytest.raises(PredicateError) as caught:
        validate_predicate(nested_predicate(op, nesting), FACTS)
    segment = '.not' if op == 'not' else f'.{op}[0]'
    assert caught.value.path == 'applies_if' + segment * 33
    assert caught.value.reason == 'too_deep'


def test_cyclic_in_memory_predicate_is_bounded():
    pred: dict = {'not': None}
    pred['not'] = pred
    with pytest.raises(PredicateError) as caught:
        validate_predicate(pred, FACTS)
    assert caught.value.path == 'applies_if' + '.not' * 33
    assert caught.value.reason == 'too_deep'


def test_allowed_ops_frozen():
    assert ALLOWED_OPS == frozenset({'all', 'any', 'not', 'eq', 'in', 'lt', 'lte', 'gt', 'gte'})
