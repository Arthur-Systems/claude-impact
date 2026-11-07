from copy import deepcopy
from pathlib import Path
import json

import pytest
from clearpath.ingestion.schemas import Manifest
from clearpath.ingestion.validation import (
    BundleValidationError, validate_bundle, validate_manifest_dict,
)
from clearpath.permits.predicates import validate_predicate

BACKEND = Path(__file__).resolve().parents[2]
FIXTURE = BACKEND / 'tests/fixtures/irvine_adu_synthetic/manifest.json'
STUB = BACKEND / 'data/irvine_adu/manifest.json'
PID = '7f9c2b1e-0000-4000-8000-000000000001'
UNKNOWN = '7f9c2b1e-0000-4000-8000-000000000099'


@pytest.fixture
def base():
    return {
        'schema_version': 1, 'kind': 'synthetic', 'jurisdiction': 'irvine-ca',
        'project_type': 'adu', 'profile_key': 'test', 'curator_label': 'SYNTHETIC TEST DATA',
        'fact_schema': {'flag': {'type': 'bool'}, 'size': {'type': 'number'},
                        'form': {'type': 'enum', 'values': ['detached']}},
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
    (['milestones', 0, 'published_clock'], {'text': 'Synthetic', 'citations': [UNKNOWN]}),
    (['conflicts'], [{'rule_keys': ['unknown'], 'source_keys': ['SYN-SOURCE'], 'summary': 'Synthetic'}]),
    (['conflicts'], [{'rule_keys': ['path'], 'source_keys': ['UNKNOWN'], 'summary': 'Synthetic'}]),
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
    (['fact_schema', 'form', 'values'], []),
    (['fact_schema', 'form', 'values'], None),
    (['fact_schema', 'flag', 'values'], ['bad']),
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
    assert any(i.path == 'requirements[0].applies_if.all[0]' for i in issues)


def test_error_redaction(base, tmp_path):
    base['passages'][0]['extra'] = 'FAKE_SECRET_SENTINEL'
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(base))
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    output = str(caught.value) + repr(caught.value.issues)
    assert base['passages'][0]['excerpt'] not in output
    assert 'FAKE_SECRET_SENTINEL' not in output
    assert caught.value.issues[0].path == 'passages[0].extra'


def test_fact_schema_key_diagnostics_do_not_leak_values(base):
    base['fact_schema']['FAKE_SECRET_SENTINEL'] = {'type': 'invalid'}
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


def test_bad_json(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{FAKE_SECRET_SENTINEL')
    with pytest.raises(BundleValidationError) as caught:
        validate_bundle(path, allowed_roots=[tmp_path])
    assert [(i.code, i.path) for i in caught.value.issues] == [('schema_invalid', '$')]
    assert 'FAKE_SECRET_SENTINEL' not in str(caught.value)


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
    stub = validate_bundle(STUB).manifest
    assert stub.kind == 'reviewed_public'
    assert not any([stub.sources, stub.passages, stub.pathways, stub.requirements, stub.milestones, stub.conflicts])
