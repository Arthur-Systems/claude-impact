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


@pytest.mark.parametrize('pred', [
    {}, [], {'unknown': []}, {'eq': ['flag', True], 'not': {}},
    {'all': []}, {'any': []}, {'not': []}, {'eq': ['flag']},
    {'eq': ['unknown', True]}, {'eq': [[], True]}, {'eq': ['flag', 1]},
    {'eq': ['size', True]}, {'eq': ['size', '500']}, {'eq': ['name', 1]},
    {'eq': ['form', 'conversion']}, {'lt': ['form', 'detached']},
    {'gte': ['flag', True]}, {'in': ['size', []]}, {'in': ['size', 1]},
    {'in': ['size', [1, False]]}, {'all': 'bad'},
])
def test_invalid_predicates(pred):
    with pytest.raises(PredicateError) as caught:
        validate_predicate(pred, FACTS)
    assert caught.value.path.startswith('applies_if')


def test_nested_path_and_no_value_leak():
    with pytest.raises(PredicateError) as caught:
        validate_predicate({'all': [{'eq': ['flag', 'FAKE_SECRET_SENTINEL']}]}, FACTS,
                           'requirements[2].applies_if')
    assert caught.value.path == 'requirements[2].applies_if.all[0]'
    assert 'FAKE_SECRET_SENTINEL' not in str(caught.value)


def test_allowed_ops_frozen():
    assert ALLOWED_OPS == frozenset({'all', 'any', 'not', 'eq', 'in', 'lt', 'lte', 'gt', 'gte'})
