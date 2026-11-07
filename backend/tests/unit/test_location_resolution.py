"""Location resolution, area mode (SPEC.md section 7). No network, no database."""

import json
from pathlib import Path

import pytest

from clearpath.locations.schemas import CoverageEntry, Jurisdiction, LocationInputError
from clearpath.locations.service import (
    load_registry,
    parse_location_input,
    resolve_location,
    slugify_city,
)

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "backend" / "tests" / "fixtures" / "api_examples"

IRVINE = Jurisdiction(slug="irvine-ca", name="Irvine")
ANAHEIM = Jurisdiction(slug="anaheim-ca", name="Anaheim")
REGISTRY = [IRVINE, ANAHEIM]
COVERAGE = {CoverageEntry("irvine-ca", "adu", "irvine-adu-detached-existing-dwelling")}


def example(name):
    return json.loads((EXAMPLES / name).read_text())


def codes(resolution):
    return [w["code"] for w in resolution.warnings]


# ---- input parsing ------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"selected_area": {"jurisdiction": "irvine-ca"}, "point": {"lat": 0, "lon": 0}},
        {"neighborhood": "x"},
        None,
        "irvine-ca",
        {"selected_area": "irvine-ca"},
        {"selected_area": {"jurisdiction": "irvine-ca", "extra": 1}},
        {"selected_area": {"jurisdiction": 5}},
        {"selected_area": {}},
    ],
)
def test_invalid_location_input(body):
    with pytest.raises(LocationInputError) as excinfo:
        parse_location_input(body)
    assert excinfo.value.code == "invalid_location_input"


def test_area_alias_is_accepted():
    assert parse_location_input({"area": {"jurisdiction": "irvine-ca"}}).mode == "selected_area"
    assert parse_location_input({"selected_area": {"jurisdiction": "irvine-ca"}}).mode == "selected_area"


# ---- area mode ----------------------------------------------------------------------


def test_area_with_coverage_matches_example_exactly():
    ex = example("locations_resolve_selected_area.json")
    result = resolve_location(ex["request"]["body"], REGISTRY, COVERAGE)
    assert result.to_dict() == ex["response"]["location"]
    ex_warning = next(w for w in ex["response"]["warnings"] if w["code"] == "selected_area_property_not_verified")
    assert ex_warning in result.warnings


def test_location_keys_match_both_examples():
    for name in ("locations_resolve_selected_area.json", "locations_resolve_ambiguous.json"):
        ex_keys = set(example(name)["response"]["location"])
        assert set(resolve_location({"area": {"jurisdiction": "irvine-ca"}}, REGISTRY, COVERAGE).to_dict()) == ex_keys


def test_registry_city_without_coverage_is_outside_supported_area():
    result = resolve_location({"area": {"jurisdiction": "anaheim-ca"}}, REGISTRY, COVERAGE)
    loc = result.to_dict()
    assert loc["status"] == "outside_supported_area"
    assert loc["status_reason"] == "no_rule_coverage"
    assert loc["jurisdiction"] == {"slug": "anaheim-ca", "name": "Anaheim"}
    assert loc["property_verified"] is False
    assert "no_rule_coverage" in codes(result)
    assert "selected_area_property_not_verified" not in codes(result)


def test_registry_membership_is_not_coverage():
    result = resolve_location({"area": {"jurisdiction": "irvine-ca"}}, REGISTRY, coverage=set())
    assert result.status == "outside_supported_area"


def test_unknown_slug_is_unresolved():
    result = resolve_location({"area": {"jurisdiction": "atlantis-ca"}}, REGISTRY, COVERAGE)
    loc = result.to_dict()
    assert loc["status"] == "unresolved"
    assert loc["status_reason"] == "unknown_jurisdiction"
    assert loc["jurisdiction"] is None


@pytest.mark.parametrize(
    "body, mode",
    [
        ({"point": {"lat": 0.0, "lon": 0.0}}, "point"),
        ({"address": {"number": "<n>", "street_name": "<s>"}}, "address"),
    ],
)
def test_point_and_address_not_implemented_yet(body, mode):
    result = resolve_location(body, REGISTRY, COVERAGE)
    loc = result.to_dict()
    assert loc["mode"] == mode
    assert loc["status"] == "unresolved"
    assert loc["status_reason"] == "mode_not_implemented"
    assert loc["jurisdiction"] is None


def test_fixture_mode_only_in_synthetic_mode():
    body = {"fixture": {"name": "synthetic-lot-1", "jurisdiction": "irvine-ca"}}
    demo = resolve_location(body, REGISTRY, COVERAGE, dataset_mode="synthetic")
    assert demo.status == "confirmed"
    assert demo.to_dict()["property_verified"] is False
    assert "synthetic_location_fixture" in codes(demo)

    real = resolve_location(body, REGISTRY, COVERAGE, dataset_mode="reviewed_public")
    assert real.status == "unresolved"
    assert real.status_reason == "fixture_requires_synthetic_mode"


# ---- registry ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, slug",
    [("Irvine", "irvine-ca"), ("Costa Mesa", "costa-mesa-ca"), ("San Juan Capistrano", "san-juan-capistrano-ca")],
)
def test_slugify_city(name, slug):
    assert slugify_city(name) == slug


def test_load_registry_from_repo_city_list():
    registry = load_registry()
    slugs = [j.slug for j in registry]
    assert len(registry) == 34
    assert len(set(slugs)) == 34
    assert "irvine-ca" in slugs
    irvine = next(j for j in registry if j.slug == "irvine-ca")
    assert irvine.name == "Irvine" and irvine.state == "CA" and irvine.timezone == "America/Los_Angeles"
