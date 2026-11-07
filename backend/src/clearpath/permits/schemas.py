"""Permit lookup request parsing and errors (SPEC.md sections 7 and 9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clearpath.locations.schemas import LocationInput, LocationInputError
from clearpath.locations.service import parse_location_input

PROJECT_TYPES = ("adu", "duplex", "multifamily", "other_housing")

LOOKUP_STATUSES = ("checklist_ready", "needs_information", "rule_coverage_unavailable", "location_unresolved")


def notice_for(city_name: str | None) -> str:
    where = f"the City of {city_name}" if city_name else "your city"
    return f"Prototype. Not legal advice. Confirm with {where} or a professional."


NOTICE = notice_for("Irvine")
"""The notice shown for Irvine results (matches the api_examples files)."""


class PermitLookupError(Exception):
    """Base error. ``code`` is machine-readable; messages never include fact values."""

    http_status = 500

    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        super().__init__(f"{code}: {message}" + (f" (at {path})" if path else ""))
        self.code = code
        self.message = message
        self.path = path


class LookupInputError(PermitLookupError):
    """Malformed or contradictory request. Route returns 422."""

    http_status = 422


class LookupUnavailable(PermitLookupError):
    """A configured profile's dataset cannot be loaded. Route returns 503."""

    http_status = 503


@dataclass(frozen=True)
class PermitLookupRequest:
    location: LocationInput
    project_type: str
    profile_key: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)


_ALLOWED_FIELDS = {"location", "project_type", "profile_key", "facts"}


def parse_permit_lookup_request(body: Any) -> PermitLookupRequest:
    if not isinstance(body, dict):
        raise LookupInputError("invalid_request", "request body must be an object")
    if not set(body) <= _ALLOWED_FIELDS:
        raise LookupInputError("invalid_request", "request has unknown fields")
    if "location" not in body or "project_type" not in body:
        raise LookupInputError("invalid_request", "'location' and 'project_type' are required")
    try:
        location = parse_location_input(body["location"])
    except LocationInputError as error:
        raise LookupInputError(error.code, error.message, "location") from None
    project_type = body["project_type"]
    if project_type not in PROJECT_TYPES:
        raise LookupInputError("invalid_project_type", "project_type must be adu, duplex, multifamily or other_housing")
    profile_key = body.get("profile_key")
    if profile_key is not None and (not isinstance(profile_key, str) or not profile_key):
        raise LookupInputError("invalid_request", "profile_key must be a non-empty string")
    facts = body.get("facts", {})
    if not isinstance(facts, dict):
        raise LookupInputError("invalid_facts", "facts must be an object")
    return PermitLookupRequest(location=location, project_type=project_type, profile_key=profile_key, facts=dict(facts))
