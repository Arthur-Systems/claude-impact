"""Resolve a location input to a city and a status (SPEC.md section 7).

Area mode is implemented. Point and address modes return ``unresolved`` /
``mode_not_implemented`` until the boundary check and the city GIS adapter are built.
Nothing here makes a network call.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from clearpath.locations.schemas import (
    INPUT_MODES,
    CoverageEntry,
    Jurisdiction,
    LocationInput,
    LocationInputError,
    LocationResolution,
)

# backend/src/clearpath/locations/service.py -> repo root is parents[4]
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[4] / "lanes" / "2-clear-it" / "data" / "oc-cities.json"


def _warning(code: str, message: str) -> dict:
    return {"code": code, "message": message}


# --------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------


def slugify_city(name: str, state: str = "CA") -> str:
    """'Costa Mesa' -> 'costa-mesa-ca'."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{base}-{state.lower()}"


def load_registry(path: Path | str | None = None) -> list[Jurisdiction]:
    """Load the city reference list from oc-cities.json. Read-only. Not rule coverage."""
    data = json.loads(Path(path or DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    return [
        Jurisdiction(slug=slugify_city(c["name"]), name=c["name"], permit_page_url=c.get("permit_page"))
        for c in data["cities"]
    ]


# --------------------------------------------------------------------------------------
# Input parsing
# --------------------------------------------------------------------------------------


def _parse_jurisdiction_ref(payload: Any, allowed: set[str]) -> None:
    if not isinstance(payload, dict) or "jurisdiction" not in payload:
        raise LocationInputError("expected an object with a 'jurisdiction' slug")
    if not set(payload) <= allowed:
        raise LocationInputError("unexpected fields in location input")
    if not isinstance(payload["jurisdiction"], str) or not payload["jurisdiction"]:
        raise LocationInputError("'jurisdiction' must be a non-empty string")


def parse_location_input(body: Any) -> LocationInput:
    """Require exactly one location mode. Raises LocationInputError (422)."""
    if isinstance(body, LocationInput):
        return body
    if not isinstance(body, dict):
        raise LocationInputError("location must be an object")
    keys = list(body)
    if len(keys) != 1:
        raise LocationInputError("give exactly one location mode: selected_area, point, address or fixture")
    key = keys[0]
    if key not in INPUT_MODES:
        raise LocationInputError("unknown location mode")
    mode = INPUT_MODES[key]
    payload = body[key]
    if mode == "selected_area":
        _parse_jurisdiction_ref(payload, {"jurisdiction"})
    elif mode == "fixture":
        _parse_jurisdiction_ref(payload, {"jurisdiction", "name"})
    elif not isinstance(payload, dict):
        raise LocationInputError(f"'{key}' must be an object")
    return LocationInput(mode=mode, payload=payload)


# --------------------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------------------


def _registry_index(registry: Iterable[Jurisdiction] | Mapping[str, Jurisdiction]) -> dict[str, Jurisdiction]:
    if isinstance(registry, Mapping):
        return dict(registry)
    return {j.slug: j for j in registry}


def _covered(slug: str, coverage: Iterable[CoverageEntry]) -> bool:
    return any(CoverageEntry(*entry).jurisdiction == slug for entry in coverage)


def resolve_location(
    location_input: Any,
    registry: Iterable[Jurisdiction] | Mapping[str, Jurisdiction],
    coverage: Iterable[CoverageEntry],
    *,
    dataset_mode: str = "reviewed_public",
) -> LocationResolution:
    """Resolve one location input.

    ``registry`` is the city reference list; ``coverage`` lists the profiles that have an
    active release. A city in the registry without coverage is ``outside_supported_area``.
    """
    loc = parse_location_input(location_input)
    cities = _registry_index(registry)
    coverage = list(coverage)

    if loc.mode in ("point", "address"):
        return LocationResolution(
            mode=loc.mode,
            status="unresolved",
            status_reason="mode_not_implemented",
            warnings=(_warning("location_mode_not_implemented",
                               "Address and map-point lookup are not built yet. Choose a city area instead."),),
        )

    slug = loc.payload["jurisdiction"]
    city = cities.get(slug)
    if city is None:
        return LocationResolution(
            mode=loc.mode,
            status="unresolved",
            status_reason="unknown_jurisdiction",
            warnings=(_warning("location_unresolved", "That city is not in the ClearPath city list."),),
        )

    if loc.mode == "fixture" and dataset_mode != "synthetic":
        return LocationResolution(
            mode=loc.mode,
            status="unresolved",
            status_reason="fixture_requires_synthetic_mode",
            warnings=(_warning("location_unresolved", "Test locations work only in synthetic demo mode."),),
        )

    if not _covered(slug, coverage):
        return LocationResolution(
            mode=loc.mode,
            status="outside_supported_area",
            status_reason="no_rule_coverage",
            jurisdiction=city,
            warnings=(_warning("no_rule_coverage",
                               f"{city.name} is in the city list, but ClearPath has no curated rules for it yet. "
                               "No checklist is shown."),),
        )

    if loc.mode == "fixture":
        return LocationResolution(
            mode="fixture",
            status="confirmed",
            status_reason="synthetic_fixture",
            jurisdiction=city,
            warnings=(_warning("synthetic_location_fixture",
                               "This is a synthetic test location, not a real property."),),
        )

    return LocationResolution(
        mode="selected_area",
        status="selected_area",
        jurisdiction=city,
        warnings=(_warning("selected_area_property_not_verified",
                           f"You chose the {city.name} area. No specific property was checked, "
                           "so results are area-level only."),),
    )
