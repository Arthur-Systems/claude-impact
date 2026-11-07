"""Pure bundle validation: no database, network, or submitted-value diagnostics."""
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from pydantic import ValidationError

from clearpath.ingestion.schemas import Manifest
from clearpath.permits.predicates import PredicateError, validate_predicate

BACKEND_DIR = Path(__file__).resolve().parents[3]
ALLOWED_ROOTS = (BACKEND_DIR / 'data', BACKEND_DIR / 'tests' / 'fixtures')


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str


class BundleValidationError(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__('; '.join(f'{issue.code}: {issue.path}' for issue in issues))


@dataclass(frozen=True)
class ValidatedBundle:
    manifest: Manifest
    content_hash: str
    manifest_path: Path


def _field_path(loc: tuple) -> str:
    result = ''
    for index, part in enumerate(loc):
        # Mapping keys are submitted data, unlike fixed model field names.
        if index == 1 and loc[0] == 'fact_schema':
            part = '*'
        if isinstance(part, int):
            result += f'[{part}]'
        else:
            result += ('.' if result else '') + str(part)
    return result or '$'


def validate_manifest_dict(data: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    # Version diagnostics survive other schema errors; never coerce a version.
    if isinstance(data, dict) and 'schema_version' in data and data['schema_version'] != 1:
        issues.append(ValidationIssue('unsupported_schema_version', 'schema_version'))
    try:
        manifest = Manifest.model_validate(data)
    except ValidationError as error:
        issues.extend(ValidationIssue('schema_invalid', _field_path(e['loc']))
                      for e in error.errors(include_input=False, include_context=False))
        return issues

    collections = {
        'sources': ('key', manifest.sources),
        'passages': ('id', manifest.passages),
        'pathways': ('key', manifest.pathways),
        'requirements': ('key', manifest.requirements),
        'milestones': ('key', manifest.milestones),
    }
    keys = {}
    for name, (field, rows) in collections.items():
        seen = set()
        for i, row in enumerate(rows):
            key = getattr(row, field)
            if key in seen:
                issues.append(ValidationIssue('duplicate_key', f'{name}[{i}].{field}'))
            seen.add(key)
        keys[name] = seen

    def reference(value: object, known: set, path: str) -> None:
        if value not in known:
            issues.append(ValidationIssue('dangling_reference', path))

    def references(values: list, known: set, path: str) -> None:
        for i, value in enumerate(values):
            reference(value, known, f'{path}[{i}]')

    for i, passage in enumerate(manifest.passages):
        reference(passage.source_key, keys['sources'], f'passages[{i}].source_key')
    for name in ('pathways', 'requirements', 'milestones'):
        for i, owner in enumerate(getattr(manifest, name)):
            path = f'{name}[{i}]'
            references(owner.citations, keys['passages'], f'{path}.citations')
            if name in ('pathways', 'requirements'):
                if manifest.kind == 'reviewed_public' and not owner.citations:
                    issues.append(ValidationIssue('missing_citation', f'{path}.citations'))
                try:
                    validate_predicate(owner.applies_if, manifest.fact_schema, f'{path}.applies_if')
                except PredicateError as error:
                    issues.append(ValidationIssue('invalid_predicate', error.path))
            if name == 'requirements':
                references(owner.pathways, keys['pathways'], f'{path}.pathways')
            if name == 'milestones':
                references(owner.predecessors, keys['milestones'], f'{path}.predecessors')
                references(owner.requirements, keys['requirements'], f'{path}.requirements')
                if owner.published_clock is not None:
                    references(owner.published_clock.citations, keys['passages'],
                               f'{path}.published_clock.citations')
    for i, conflict in enumerate(manifest.conflicts):
        references(conflict.rule_keys, keys['pathways'] | keys['requirements'],
                   f'conflicts[{i}].rule_keys')
        references(conflict.source_keys, keys['sources'], f'conflicts[{i}].source_keys')

    # Kahn's algorithm on existing nodes only: dangling edges are reported above,
    # not misclassified as cycles. Sets make repeated edges idempotent.
    predecessors = {key: set() for key in keys['milestones']}
    for milestone in manifest.milestones:
        predecessors[milestone.key].update(set(milestone.predecessors) & keys['milestones'])
    successors = {key: set() for key in predecessors}
    for key, parents in predecessors.items():
        for parent in parents:
            successors[parent].add(key)
    degree = {key: len(parents) for key, parents in predecessors.items()}
    ready = deque(key for key, count in degree.items() if count == 0)
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for child in successors[key]:
            degree[child] -= 1
            if degree[child] == 0:
                ready.append(child)
    if visited != len(predecessors):
        issues.append(ValidationIssue('cyclic_milestones', 'milestones'))
    return issues


def validate_bundle(
    path: Path | str, *, allowed_roots: Sequence[Path] | None = None
) -> ValidatedBundle:
    resolved = Path(path).resolve()
    roots = ALLOWED_ROOTS if allowed_roots is None else allowed_roots
    if not any(resolved.is_relative_to(Path(root).resolve()) for root in roots):
        raise BundleValidationError([ValidationIssue('path_outside_bundle', '$')])
    try:
        data = json.loads(resolved.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise BundleValidationError([ValidationIssue('schema_invalid', '$')]) from None
    issues = validate_manifest_dict(data)
    if issues:
        raise BundleValidationError(issues)
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return ValidatedBundle(
        manifest=Manifest.model_validate(data),
        content_hash=sha256(canonical.encode('utf-8')).hexdigest(),
        manifest_path=resolved,
    )
