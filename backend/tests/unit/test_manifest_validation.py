from copy import deepcopy
from pathlib import Path
import json

import pytest
from clearpath.ingestion.schemas import Manifest
from clearpath.ingestion.validation import (
    BundleValidationError, ValidationIssue, validate_bundle, validate_manifest_dict,
)
from clearpath.permits.predicates import ADU_FACT_SCHEMA, MAX_DEPTH, validate_predicate

BACKEND = Path(__file__).resolve().parents[2]
FIXTURE = BACKEND / 'tests/fixtures/irvine_adu_synthetic/manifest.json'
REVIEWED_PUBLIC = BACKEND / 'data/irvine_adu/manifest.json'
PID = '7f9c2b1e-0000-4000-8000-000000000001'
UNKNOWN = '7f9c2b1e-0000-4000-8000-000000000099'
CLOCK = {
    'kind': 'city_service_target', 'value': 2, 'unit': 'business_days',
    'scope': 'SYNTHETIC display-only timing scope',
}


@pytest.fixture
def base():
    return {
        'schema_version': 1, 'kind': 'synthetic', 'jurisdiction': 'irvine-ca',
        'project_type': 'adu', 'profile_key': 'test', 'curator_label': 'SYNTHETIC TEST DATA',
        'fact_schema': {'flag': 'boolean', 'size': 'number', 'form': 'string'},
        'sources': [{'key': 'SYN-SOURCE', 'url': 'https://example.org/synthetic',
                     'title': 'SYNTHETIC TEST SOURCE', 'publisher': 'Synthetic',
                     'authority_type': 'synthetic', 'checked_at': '2026-11-07',
                     'sha256': None, 'verification_depth': 'title_only', 'terms_note': None}],
        'passages': [{'id': PID, 'source_key': 'SYN-SOURCE', 'locator': '#test',
                      'excerpt': 'SYNTHETIC: private excerpt sentinel', 'review_status': 'reviewed'}],
        'pathways': [{'key': 'path', 'title': 'Synthetic path', 'description': 'Synthetic',
                      'applies_if': {'eq': ['flag', True]}, 'citations': [PID]}],
        'requirements': [{'key': 'doc', 'pathways': ['path'], 'kind': 'document',
                          'title': 'Synthetic document', 'description': 'Synthetic',
                          'applies_if': {'gt': ['size', 500]},
                          'required_for_preparation': True, 'citations': [PID]}],
        'milestones': [{'key': 'prepare', 'title': 'Synthetic preparation',
                        'predecessors': [], 'requirements': ['doc'], 'published_clock': None,
                        'assumed_days': {'min': 0, 'max': 1, 'label': 'ASSUMPTION',
                                         'rationale': 'synthetic test value'}, 'citations': [PID]}],
        'conflicts': [],
    }


def set_at(data, path, value):
    for part in path[:-1]:
        data = data[part]
    data[path[-1]] = value


@pytest.mark.parametrize(('code', 'path', 'value'), [
    ('schema_invalid', ['jurisdiction'], 'BAD SLUG'),
    ('unsupported_schema_version', ['schema_version'], 2),
    ('dangling_reference', ['passages', 0, 'source_key'], 'UNKNOWN'),
    ('invalid_predicate', ['requirements', 0, 'applies_if'], {'all': []}),
    ('cyclic_milestones', ['milestones', 0, 'predecessors'], ['prepare']),
])
def test_error_codes(base, code, path, value):
    bad = deepcopy(base)
    set_at(bad, path, value)
    assert code in {issue.code for issue in validate_manifest_dict(bad)}


@pytest.mark.parametrize('collection', ['sources', 'passages', 'pathways', 'requirements', 'milestones'])
def test_duplicate_keys(base, collection):
    base[collection].append(deepcopy(base[collection][0]))
    assert 'duplicate_key' in {i.code for i in validate_manifest_dict(base)}


@pytest.mark.parametrize(('path', 'value'), [
    (['pathways', 0, 'citations'], [UNKNOWN]),
    (['requirements', 0, 'citations'], [UNKNOWN]),
    (['requirements', 0, 'pathways'], ['unknown']),
    (['milestones', 0, 'predecessors'], ['unknown']),
    (['milestones', 0, 'requirements'], ['unknown']),
    (['milestones', 0, 'citations'], [UNKNOWN]),
    (['milestones', 0, 'published_clock'], {**CLOCK, 'citation': UNKNOWN}),
    (['milestones', 0, 'published_clock'], {**CLOCK, 'citations': [UNKNOWN]}),
])
def test_all_reference_types(base, path, value):
    set_at(base, path, value)
    assert 'dangling_reference' in {i.code for i in validate_manifest_dict(base)}


@pytest.mark.parametrize('owner', ['pathways', 'requirements'])
def test_missing_citation_only_public(base, owner):
    base[owner][0]['citations'] = []
    assert validate_manifest_dict(base) == []
    base['kind'] = 'reviewed_public'
    assert 'missing_citation' in {i.code for i in validate_manifest_dict(base)}


@pytest.mark.parametrize(('path', 'value'), [
    (['fact_schema', 'form'], {'type': 'enum', 'values': ['detached']}),
    (['fact_schema', 'flag'], 'bool'),
    (['fact_schema', 'size'], 'invalid'),
    (['sources', 0, 'url'], 'http://example.org'),
    (['sources', 0, 'url'], 'https://user:password@example.org'),
    (['sources', 0, 'url'], 'https:///missing-host'),
    (['sources', 0, 'sha256'], 'A' * 64),
    (['passages', 0, 'locator'], ''),
    (['passages', 0, 'excerpt'], ''),
    (['requirements', 0, 'pathways'], []),
    (['milestones', 0, 'assumed_days', 'min'], -1),
    (['milestones', 0, 'assumed_days', 'max'], -1),
    (['milestones', 0, 'assumed_days', 'min'], 2),
    (['milestones', 0, 'assumed_days', 'rationale'], ''),
    (['milestones', 0, 'assumed_days', 'label'], 'UNMARKED'),
    (['pathways', 0, 'extra'], 'not allowed'),
    (['conflicts'], [{'rule_keys': [], 'source_keys': ['SYN-SOURCE'], 'summary': 'Synthetic'}]),
])
def test_schema_rules(base, path, value):
    set_at(base, path, value)
    assert 'schema_invalid' in {i.code for i in validate_manifest_dict(base)}


def test_valid_in_memory_and_fact_models(base):
    assert validate_manifest_dict(base) == []
    manifest = Manifest.model_validate(base)
    validate_predicate({'eq': ['flag', True]}, manifest.fact_schema)
    base['conflicts'] = [{'rule_keys': ['path', 'doc'], 'source_keys': ['SYN-SOURCE'], 'summary': 'Synthetic'}]
    assert validate_manifest_dict(base) == []


def test_collects_all_issues_and_nested_path(base):
    base['requirements'][0]['applies_if'] = {'all': [{'eq': ['flag', 1]}]}
    base['passages'][0]['source_key'] = 'UNKNOWN'
    issues = validate_manifest_dict(base)
    assert {i.code for i in issues} == {'invalid_predicate', 'dangling_reference'}
    assert any(i.path == 'requirements[0].applies_if.all[0].eq'
               and i.reason == 'type_mismatch' for i in issues)


@pytest.mark.parametrize(('predicate', 'suffix', 'reason'), [
    ({'eq': ['flag', 'SENTINEL\nX']}, '.eq', 'type_mismatch'),
    ({'SENTINEL\nX': []}, '', 'unknown_operator'),
    ({'not': []}, '.not', 'invalid_operands'),
    ({'eq': ['SENTINEL\nX', True]}, '.eq', 'unknown_fact'),
])
def test_manifest_propagates_predicate_path_and_static_reason(base, tmp_path, predicate, suffix, reason):
    base['requirements'].append(deepcopy(base['requirements'][0]))
    base['requirements'][1]['key'] = 'other-doc'
    base['requirements'][1]['applies_if'] = {'all': [predicate]}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base), encoding='utf-8')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    expected_path = f'requirements[1].applies_if.all[0]{suffix}'
    assert [(i.code, i.path, i.reason) for i in caught.value.issues] == [
        ('invalid_predicate', expected_path, reason),
    ]
    assert str(caught.value) == f'invalid_predicate: {expected_path} ({reason})'
    assert 'SENTINEL' not in str(caught.value)
    assert '\n' not in str(caught.value)


def test_adu_fact_schema_defaults_to_shared_plain_string_types(base):
    del base['fact_schema']
    base['pathways'][0]['applies_if'] = {'eq': ['adu_form', 'detached']}
    base['requirements'][0]['applies_if'] = {'eq': ['existing_dwelling', True]}
    assert validate_manifest_dict(base) == []
    manifest = Manifest.model_validate(base)
    assert manifest.fact_schema == {key: kind.value for key, kind in ADU_FACT_SCHEMA.items()}
    assert all(type(kind) is str for kind in manifest.fact_schema.values())
    assert 'fact_schema' not in base


@pytest.mark.parametrize('project_type', ['duplex', 'multifamily', 'other_housing'])
def test_non_adu_requires_explicit_fact_schema(base, project_type):
    base['project_type'] = project_type
    assert validate_manifest_dict(base) == []
    del base['fact_schema']
    assert validate_manifest_dict(base) == [ValidationIssue('schema_invalid', 'fact_schema', 'missing')]


@pytest.mark.parametrize('value', [None, {'flag': {'type': 'bool'}}])
def test_explicit_invalid_fact_schema_is_not_defaulted(base, value):
    base['fact_schema'] = value
    assert 'schema_invalid' in {i.code for i in validate_manifest_dict(base)}


def test_pathway_description_defaults_to_empty_without_mutating_input(base):
    del base['pathways'][0]['description']
    original = deepcopy(base)
    assert validate_manifest_dict(base) == []
    assert Manifest.model_validate(base).pathways[0].description == ''
    assert base == original


def test_optional_manifest_metadata_and_required_profile_key(base):
    del base['kind']
    del base['curator_label']
    base['subtype'] = 'detached_adu_existing_dwelling'
    assert validate_manifest_dict(base) == []
    manifest = Manifest.model_validate(base)
    assert manifest.kind == 'reviewed_public'
    assert manifest.curator_label == ''
    assert manifest.subtype == base['subtype']
    del base['profile_key']
    assert validate_manifest_dict(base) == [ValidationIssue('schema_invalid', 'profile_key', 'missing')]


def test_curator_notes_are_ignored_at_every_level_without_mutating_input(base, tmp_path):
    base['conflicts'] = [{'rule_keys': ['path'], 'source_keys': ['SYN-SOURCE'], 'summary': 'Synthetic'}]
    base['milestones'][0]['published_clock'] = {**CLOCK, 'citations': [PID]}
    expected = Manifest.model_validate(base).model_dump(mode='json')
    pending = [base]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            pending.extend(node.values())
            node['_SENTINEL\nX'] = {'secret': 'NOTE_VALUE_SENTINEL'}
        elif isinstance(node, list):
            pending.extend(node)
    original = deepcopy(base)
    assert validate_manifest_dict(base) == []
    assert Manifest.model_validate(base).model_dump(mode='json') == expected
    assert base == original
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base), encoding='utf-8')
    first = validate_bundle(path, allowed_roots=[tmp_path])
    from hashlib import sha256
    canonical = json.dumps(base, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    assert first.content_hash == sha256(canonical.encode('utf-8')).hexdigest()
    base['_SENTINEL\nX'] = 'changed note'
    path.write_text(json.dumps(base), encoding='utf-8')
    second = validate_bundle(path, allowed_roots=[tmp_path])
    assert first.manifest == second.manifest
    assert first.content_hash != second.content_hash


def test_curator_note_keys_and_values_never_appear_in_diagnostics(base, tmp_path):
    base['_SENTINEL\nX'] = 'NOTE_VALUE_SENTINEL'
    base['passages'][0]['_review_note'] = 'PRIVATE_REVIEW_SENTINEL'
    base['passages'][0]['unexpected'] = 'BAD_VALUE_SENTINEL'
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base), encoding='utf-8')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert caught.value.issues == [ValidationIssue('schema_invalid', 'passages[0].*', 'extra_forbidden')]
    assert str(caught.value) == 'schema_invalid: passages[0].* (extra_forbidden)'
    assert 'SENTINEL' not in repr(caught.value.issues)


@pytest.mark.parametrize(('note', 'expected'), [
    (None, 'reviewed'), ('', 'reviewed'), ('Needs a hand check', 'needs_review'),
])
def test_passage_review_status_defaults_from_review_note(base, note, expected):
    passage = base['passages'][0]
    del passage['review_status']
    if note is not None:
        passage['_review_note'] = note
    original = deepcopy(base)
    assert validate_manifest_dict(base) == []
    manifest = Manifest.model_validate(base)
    assert manifest.passages[0].review_status == expected
    assert '_review_note' not in manifest.passages[0].model_dump()
    assert base == original


@pytest.mark.parametrize('status', ['reviewed', 'needs_review', 'failed'])
def test_explicit_passage_review_status_wins_over_review_note(base, status):
    base['passages'][0]['_review_note'] = 'Needs a hand check'
    base['passages'][0]['review_status'] = status
    assert validate_manifest_dict(base) == []
    assert Manifest.model_validate(base).passages[0].review_status == status


def test_invalid_explicit_review_status_is_not_defaulted(base):
    base['passages'][0]['_review_note'] = 'Needs a hand check'
    base['passages'][0]['review_status'] = None
    assert validate_manifest_dict(base) == [
        ValidationIssue('schema_invalid', 'passages[0].review_status', 'literal_error'),
    ]


@pytest.mark.parametrize('kind', ['city_service_target', 'statutory_clock', 'observed', 'assumption'])
@pytest.mark.parametrize('evidence', [{'citation': PID}, {'citations': [PID]}, {'citation': PID, 'citations': [PID]}])
@pytest.mark.parametrize('value', [2, 0.5, None])
def test_published_clock_accepts_timing_objects(base, kind, evidence, value):
    clock = {**CLOCK, 'kind': kind, 'value': value, **evidence}
    base['milestones'][0]['published_clock'] = clock
    original = deepcopy(base)
    assert validate_manifest_dict(base) == []
    parsed = Manifest.model_validate(base).milestones[0].published_clock
    assert parsed is not None
    assert parsed.model_dump(mode='json', exclude_unset=True) == clock
    assert parsed.qualifier is None and parsed.verification is None
    assert base == original


@pytest.mark.parametrize('kind', ['city_service_target', 'statutory_clock'])
@pytest.mark.parametrize('evidence', [{}, {'citation': None}, {'citations': []}, {'citation': None, 'citations': []}])
def test_published_guidance_requires_a_clock_citation(base, kind, evidence):
    base['milestones'][0]['published_clock'] = {**CLOCK, 'kind': kind, **evidence}
    assert 'schema_invalid' in {issue.code for issue in validate_manifest_dict(base)}


@pytest.mark.parametrize('kind', ['observed', 'assumption'])
def test_other_timing_kinds_allow_unknown_uncited_values(base, kind):
    base['milestones'][0]['published_clock'] = {**CLOCK, 'kind': kind, 'value': None}
    assert validate_manifest_dict(base) == []
    parsed = Manifest.model_validate(base).milestones[0].published_clock
    assert parsed is not None
    assert parsed.citation is None and parsed.citations == []


@pytest.mark.parametrize(('field', 'value'), [
    ('value', float('nan')), ('value', float('inf')), ('value', -float('inf')),
    ('value', True), ('value', '2'), ('scope', ''), ('kind', 'deadline'),
    ('citation', 'PRIVATE_SENTINEL'), ('citations', ['PRIVATE_SENTINEL']),
])
def test_invalid_timing_values_have_safe_schema_diagnostics(base, field, value):
    base['milestones'][0]['published_clock'] = {**CLOCK, 'citation': PID, field: value}
    issues = validate_manifest_dict(base)
    assert issues and {issue.code for issue in issues} == {'schema_invalid'}
    assert all(issue.path.startswith('milestones[0].published_clock') for issue in issues)
    assert 'PRIVATE_SENTINEL' not in str(BundleValidationError(issues))


@pytest.mark.parametrize('omit_rationale', [False, True])
def test_unknown_assumed_days_allows_null_or_omitted_rationale(base, omit_rationale):
    days = {'min': None, 'max': None, 'label': 'ASSUMPTION'}
    if not omit_rationale:
        days['rationale'] = None
    base['milestones'][0]['assumed_days'] = days
    assert validate_manifest_dict(base) == []
    assumed = Manifest.model_validate(base).milestones[0].assumed_days
    assert assumed is not None and assumed.rationale is None


@pytest.mark.parametrize(('minimum', 'maximum'), [(0, None), (None, 1), (0, 1)])
@pytest.mark.parametrize('omit_rationale', [False, True])
def test_assumed_days_with_a_bound_requires_rationale(base, minimum, maximum, omit_rationale):
    days = {'min': minimum, 'max': maximum, 'label': 'ASSUMPTION'}
    if not omit_rationale:
        days['rationale'] = None
    base['milestones'][0]['assumed_days'] = days
    assert 'schema_invalid' in {i.code for i in validate_manifest_dict(base)}
    days['rationale'] = 'synthetic test value'
    assert validate_manifest_dict(base) == []


@pytest.mark.parametrize('field', ['source_keys', 'sources'])
def test_conflicts_accept_informational_keys_without_resolving_references(base, field):
    rule_keys = ['hold-harmless-affidavit (not entered)', 'prepare', 'unentered rule']
    source_keys = ['SPEC-8', 'not a source slug']
    base['conflicts'] = [{'rule_keys': rule_keys, field: source_keys, 'summary': 'Synthetic'}]
    original = deepcopy(base)
    assert validate_manifest_dict(base) == []
    assert Manifest.model_validate(base).conflicts[0].model_dump() == {
        'rule_keys': rule_keys, 'source_keys': source_keys, 'summary': 'Synthetic',
    }
    assert base == original
    assert Manifest.model_validate(base).conflicts[0].model_dump(mode='json', round_trip=True) == base['conflicts'][0]


@pytest.mark.parametrize(('field', 'value'), [
    ('rule_keys', []), ('rule_keys', ['']), ('rule_keys', [1]),
    ('source_keys', []), ('source_keys', ['']), ('source_keys', [1]),
    ('sources', []), ('sources', ['']), ('sources', [1]), ('summary', ''),
])
def test_conflicts_require_nonempty_strings_without_echoing_informational_text(base, field, value):
    source_field = 'sources' if field == 'sources' else 'source_keys'
    conflict = {'rule_keys': ['PRIVATE_RULE_SENTINEL (not entered)'],
                source_field: ['PRIVATE_SOURCE_SENTINEL'], 'summary': 'PRIVATE_SUMMARY_SENTINEL'}
    conflict[field] = value
    base['conflicts'] = [conflict]
    issues = validate_manifest_dict(base)
    assert issues and {issue.code for issue in issues} == {'schema_invalid'}
    assert all(issue.path.startswith('conflicts[0].') for issue in issues)
    assert 'SENTINEL' not in str(BundleValidationError(issues))
    assert 'SENTINEL' not in repr(issues)


@pytest.mark.parametrize('fields', [{}, {'sources': ['SYN-SOURCE'], 'source_keys': ['SYN-SOURCE']}])
def test_conflict_requires_exactly_one_source_key_spelling(base, fields):
    base['conflicts'] = [{'rule_keys': ['path'], 'summary': 'Synthetic', **fields}]
    assert 'schema_invalid' in {i.code for i in validate_manifest_dict(base)}


def test_error_redaction(base, tmp_path):
    base['passages'][0]['extra'] = 'FAKE_SECRET_SENTINEL'
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base))
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    output = str(caught.value) + repr(caught.value.issues)
    assert base['passages'][0]['excerpt'] not in output
    assert 'FAKE_SECRET_SENTINEL' not in output
    assert caught.value.issues[0].path == 'passages[0].*'


@pytest.mark.parametrize(('owner', 'key', 'expected_path'), [
    ([], 'excerpt', '*'),
    ([], 'type', '*'),  # Not a manifest field.
    (['passages', 0], 'SENTINEL\nX\x1b\x7f', 'passages[0].*'),
    (['passages', 0], 'description', 'passages[0].*'),
    (['milestones', 0, 'assumed_days'], 'SENTINEL\nX', 'milestones[0].assumed_days.*'),
])
def test_schema_diagnostics_mask_unknown_field_names(base, tmp_path, owner, key, expected_path):
    key = base['passages'][0]['excerpt'] if key == 'excerpt' else key
    target = base
    for part in owner:
        target = target[part]
    target[key] = 'FAKE_SECRET_VALUE'
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base), encoding='utf-8')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert [issue.path for issue in caught.value.issues] == [expected_path]
    assert [issue.reason for issue in caught.value.issues] == ['extra_forbidden']
    assert str(caught.value) == f'schema_invalid: {expected_path} (extra_forbidden)'
    assert key not in str(caught.value)
    assert key not in repr(caught.value.issues)
    assert 'FAKE_SECRET_VALUE' not in str(caught.value)
    assert all(ord(c) >= 32 and ord(c) != 127 for c in str(caught.value))


@pytest.mark.parametrize('key', ['FAKE_SECRET_SENTINEL', 'SENTINEL\nX', 'type'])
def test_fact_schema_keys_are_masked_even_when_they_match_field_names(base, key):
    base['fact_schema'][key] = 'invalid'
    issues = validate_manifest_dict(base)
    assert issues
    assert {issue.path for issue in issues} <= {'fact_schema.*.*', 'fact_schema.*'}
    assert all(issue.reason for issue in issues)


@pytest.mark.parametrize(('path', 'value', 'expected_path', 'reason'), [
    (['jurisdiction'], 'BAD\nSLUG', 'jurisdiction', 'string_pattern_mismatch'),
    (['sources', 0, 'key'], 'lowercase', 'sources[0].key', 'string_pattern_mismatch'),
    (['milestones', 0, 'assumed_days', 'min'], 'bad', 'milestones[0].assumed_days.min', 'int_type'),
    (['fact_schema', 'flag'], 'bad', 'fact_schema.*', 'literal_error'),
])
def test_schema_diagnostics_keep_static_reasons(base, path, value, expected_path, reason):
    set_at(base, path, value)
    issues = validate_manifest_dict(base)
    assert [(i.code, i.path, i.reason) for i in issues] == [('schema_invalid', expected_path, reason)]


def test_missing_field_reason_and_backwards_compatible_issue_default(base):
    del base['passages'][0]['locator']
    issues = validate_manifest_dict(base)
    assert [(i.path, i.reason) for i in issues] == [('passages[0].locator', 'missing')]
    assert ValidationIssue('dangling_reference', 'passages[0].source_key').reason == ''


def test_fact_schema_key_diagnostics_do_not_leak_values(base):
    base['fact_schema']['FAKE_SECRET_SENTINEL'] = 'invalid'
    issues = validate_manifest_dict(base)
    assert issues
    assert 'FAKE_SECRET_SENTINEL' not in repr(issues)


def test_files_and_content_hash(base, tmp_path):
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base))
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path)
    assert [i.code for i in caught.value.issues] == ['path_outside_bundle']
    first = validate_bundle(path, allowed_roots=[tmp_path])
    path.write_text(json.dumps(dict(reversed(list(base.items()))), indent=2))
    assert validate_bundle(path, allowed_roots=[tmp_path]).content_hash == first.content_hash
    assert len(first.content_hash) == 64
    assert first.manifest_path == path.resolve()


def test_path_checked_before_read_and_symlinks(tmp_path):
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(tmp_path / 'nonexistent.json')
    assert caught.value.issues[0].code == 'path_outside_bundle'
    allowed = tmp_path / 'allowed'
    allowed.mkdir()
    outside = tmp_path / 'outside.json'
    outside.write_text('{}')
    (allowed / 'link.json').symlink_to(outside)
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(allowed / 'link.json', allowed_roots=[allowed])
    assert caught.value.issues[0].code == 'path_outside_bundle'


@pytest.mark.parametrize('error_type', [RuntimeError, OSError])
@pytest.mark.parametrize('failure_target', ['manifest', 'root'])
def test_path_resolution_failures_are_sanitized(tmp_path, monkeypatch, error_type, failure_target):
    root = tmp_path / 'allowed'
    root.mkdir()
    path = root / 'manifest.json'
    path.write_text('{}', encoding='utf-8')
    failing_path = path if failure_target == 'manifest' else root
    original_resolve = Path.resolve

    def fail_resolution(self, *args, **kwargs):
        if self == failing_path:
            raise error_type(f'SENTINEL\nX: {failing_path}')
        return original_resolve(self, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(Path, 'resolve', fail_resolution)
        with pytest.raises(BundleValidationError) as caught:
            validate_bundle(path, allowed_roots=[root])
    assert [(i.code, i.path) for i in caught.value.issues] == [('path_outside_bundle', '$')]
    assert str(caught.value) == 'path_outside_bundle: $'
    assert 'SENTINEL' not in str(caught.value)
    assert str(tmp_path) not in str(caught.value)
    assert caught.value.__suppress_context__


@pytest.mark.parametrize('loop_target', ['manifest', 'root'])
def test_real_symlink_loops_are_sanitized(tmp_path, loop_target):
    loop = tmp_path / 'loop'
    loop.symlink_to(loop.name)
    path = loop if loop_target == 'manifest' else tmp_path / 'manifest.json'
    root = tmp_path if loop_target == 'manifest' else loop
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[root])
    assert [(i.code, i.path) for i in caught.value.issues] == [('path_outside_bundle', '$')]
    assert str(caught.value) == 'path_outside_bundle: $'
    assert str(tmp_path) not in str(caught.value)


def test_bad_json(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{FAKE_SECRET_SENTINEL')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert [(i.code, i.path) for i in caught.value.issues] == [('schema_invalid', '$')]
    assert 'FAKE_SECRET_SENTINEL' not in str(caught.value)


@pytest.mark.parametrize('constant', ['NaN', 'Infinity', '-Infinity'])
@pytest.mark.parametrize('location', ['$', 'curator_label', 'predicate', 'extra'])
def test_non_standard_json_constants_are_rejected_anywhere(base, tmp_path, constant, location):
    marker = 'NON_STANDARD_CONSTANT_SENTINEL'
    if location == '$':
        payload = constant
    else:
        if location == 'predicate':
            base['requirements'][0]['applies_if'] = {'eq': ['size', marker]}
        else:
            base[location] = marker
        payload = json.dumps(base).replace(json.dumps(marker), constant)
    path = tmp_path / 'manifest.json'
    path.write_text(payload, encoding='utf-8')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert [(i.code, i.path, i.reason) for i in caught.value.issues] == [
        ('schema_invalid', '$', 'non_standard_json_constant'),
    ]
    assert str(caught.value) == 'schema_invalid: $ (non_standard_json_constant)'


def test_in_memory_non_finite_predicate_has_static_reason(base):
    base['requirements'][0]['applies_if'] = {'eq': ['size', float('nan')]}
    issues = validate_manifest_dict(base)
    assert [(i.code, i.path, i.reason) for i in issues] == [
        ('invalid_predicate', 'requirements[0].applies_if.eq', 'non_finite_number'),
    ]


def test_json_constant_names_inside_strings_remain_valid(base, tmp_path):
    base['curator_label'] = 'NaN Infinity -Infinity'
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base), encoding='utf-8')
    assert validate_bundle(path, allowed_roots=[tmp_path]).manifest.curator_label == base['curator_label']


def test_manifest_predicate_depth_is_bounded(base, tmp_path):
    pred = {'eq': ['flag', True]}
    for _ in range(33):
        pred = {'not': pred}
    base['requirements'][0]['applies_if'] = pred
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base), encoding='utf-8')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert [(i.code, i.path, i.reason) for i in caught.value.issues] == [
        ('invalid_predicate', 'requirements[0].applies_if' + '.not' * MAX_DEPTH, 'max_depth_exceeded'),
    ]


@pytest.mark.parametrize('surrogate', ['\ud800', '\udfff'], ids=['high-surrogate', 'low-surrogate'])
@pytest.mark.parametrize('location', ['curator_label', 'excerpt', 'predicate', 'unknown_key'])
def test_lone_surrogates_are_sanitized_before_hashing(base, tmp_path, surrogate, location):
    text = f'SENTINEL{surrogate}'
    if location == 'excerpt':
        base['passages'][0]['excerpt'] = text
    elif location == 'predicate':
        base['fact_schema']['label'] = 'string'
        base['requirements'][0]['applies_if'] = {'eq': ['label', text]}
    elif location == 'unknown_key':
        base[text] = True
    else:
        base[location] = text
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base, ensure_ascii=True), encoding='utf-8')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert [(i.code, i.path, i.reason) for i in caught.value.issues] == [
        ('schema_invalid', '$', 'invalid_unicode'),
    ]
    assert str(caught.value) == 'schema_invalid: $ (invalid_unicode)'
    assert 'SENTINEL' not in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_excessive_json_nesting_has_a_sanitized_depth_error(base, tmp_path):
    marker = 'DEEP_PREDICATE_SENTINEL'
    base['requirements'][0]['applies_if'] = marker
    deep_predicate = '{"not":' * 10000 + '{"eq":["flag",true]}' + '}' * 10000
    payload = json.dumps(base).replace(json.dumps(marker), deep_predicate)
    path = tmp_path / 'manifest.json'
    path.write_text(payload, encoding='utf-8')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert [(i.code, i.path, i.reason) for i in caught.value.issues] == [
        ('schema_invalid', '$', 'too_deep'),
    ]
    assert str(caught.value) == 'schema_invalid: $ (too_deep)'


def test_non_utf8_file_has_sanitized_root_error(tmp_path):
    path = tmp_path / 'manifest.json'
    path.write_bytes(b'{"curator_label":"SENTINEL\xff"}')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert [(i.code, i.path) for i in caught.value.issues] == [('schema_invalid', '$')]
    assert 'SENTINEL' not in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_valid_unicode_hash_does_not_depend_on_json_escape_style(base, tmp_path):
    base['curator_label'] = 'SYNTHETIC: café 🏠'
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base, ensure_ascii=True), encoding='utf-8')
    escaped = validate_bundle(path, allowed_roots=[tmp_path])
    path.write_text(json.dumps(base, ensure_ascii=False), encoding='utf-8')
    literal = validate_bundle(path, allowed_roots=[tmp_path])
    assert escaped.content_hash == literal.content_hash
    assert literal.manifest.curator_label == base['curator_label']


def test_seed_bundles():
    synthetic = validate_bundle(FIXTURE).manifest
    assert synthetic.kind == 'synthetic'
    assert len(synthetic.requirements) == 3
    assert len(synthetic.milestones) == 6
    assert synthetic.milestones[0].key == 'application_preparation'
    assert all(p.excerpt.startswith('SYNTHETIC:') for p in synthetic.passages)
    cited = {p for owner in [*synthetic.pathways, *synthetic.requirements, *synthetic.milestones] for p in owner.citations}
    assert any(p.review_status == 'needs_review' and p.id not in cited for p in synthetic.passages)
    assert all(p.review_status == 'reviewed' for p in synthetic.passages if p.id in cited)
    assert all(m.assumed_days.label == 'ASSUMPTION' for m in synthetic.milestones)
    assert synthetic.milestones[0].requirements == [r.key for r in synthetic.requirements if r.required_for_preparation]


def test_real_reviewed_public_manifest_validates_with_review_notes_preserved_as_status():
    data = json.loads(REVIEWED_PUBLIC.read_text(encoding='utf-8'))
    assert validate_manifest_dict(data) == []
    manifest = validate_bundle(REVIEWED_PUBLIC).manifest
    assert manifest.kind == 'reviewed_public'
    assert manifest.profile_key == 'irvine-adu-detached-existing-dwelling'
    assert (len(manifest.sources), len(manifest.passages), len(manifest.requirements),
            len(manifest.milestones)) == (9, 29, 10, 6)
    noted_ids = {p['id'] for p in data['passages'] if p.get('_review_note')}
    assert noted_ids
    needs_review = {str(p.id) for p in manifest.passages if p.review_status == 'needs_review'}
    assert needs_review == noted_ids
    assert len(needs_review) == sum(bool(p.get('_review_note')) for p in data['passages'])
    for index in (2, 4):
        clock = manifest.milestones[index].published_clock
        assert clock is not None
        assert clock.model_dump(mode='json', exclude_unset=True) == data['milestones'][index]['published_clock']


def test_empty_reviewed_public_stub_is_valid_in_memory(base):
    stub = deepcopy(base)
    stub['kind'] = 'reviewed_public'
    collections = ('sources', 'passages', 'pathways', 'requirements', 'milestones', 'conflicts')
    for name in collections:
        stub[name] = []
    assert validate_manifest_dict(stub) == []
    manifest = Manifest.model_validate(stub)
    assert manifest.kind == 'reviewed_public'
    assert not any(getattr(manifest, name) for name in collections)


@pytest.mark.parametrize('key', ['A', '0', 'IRV-ADU', 'IRV_ADU-01', 'A' * 80])
def test_uppercase_source_keys_remain_valid(base, key):
    base['sources'][0]['key'] = key
    base['passages'][0]['source_key'] = key
    assert validate_manifest_dict(base) == []


@pytest.mark.parametrize('key', ['a', 'irv-adu', '_IRV', '-IRV', 'A' * 81, 'IRV\nADU', 'IRV.ADU'])
def test_source_keys_reject_lowercase_or_invalid_pattern(base, key):
    base['sources'][0]['key'] = key
    assert [(i.code, i.path, i.reason) for i in validate_manifest_dict(base)] == [
        ('schema_invalid', 'sources[0].key', 'string_pattern_mismatch'),
    ]
