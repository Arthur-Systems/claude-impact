"""HTTP routes for location resolve and permit lookup (SPEC.md section 9).

Uses a tiny FastAPI app that mounts only the lookup router, with a fake API-key
dependency, the same way Person 3's app will. All data is SYNTHETIC unless a test says
otherwise. "test-key-123" is a throwaway test value, not a real key.
"""

import json
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI, Header, Request
from fastapi.testclient import TestClient

from clearpath.locations.schemas import CoverageEntry, Jurisdiction
from clearpath.locations.service import load_registry
from clearpath.permits.dev_server import (
    DevServerConfigError,
    build_from_env,
    create_dev_app,
    load_real_draft_provider,
    load_synthetic_provider,
)
from clearpath.permits.release import InMemoryReleaseProvider
from clearpath.permits.routes import ApiError, build_lookup_router

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "backend" / "tests" / "fixtures" / "api_examples"
KEY = "test-key-123"
HEADERS = {"X-API-Key": KEY}
PROFILE = "irvine-adu-detached-existing-dwelling"

C01 = {
    "location": {"selected_area": {"jurisdiction": "irvine-ca"}},
    "project_type": "adu",
    "facts": {"adu_form": "detached", "existing_dwelling": True},
}


def fake_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if x_api_key != KEY:
        raise ApiError("unauthorized", "A valid API key is required.", http_status=401)


def make_app(provider=None, registry=None, *, state_request_id=None):
    app = FastAPI()
    if state_request_id:
        @app.middleware("http")
        async def set_id(request: Request, call_next):
            request.state.request_id = state_request_id
            return await call_next(request)
    router = build_lookup_router(provider or load_synthetic_provider(), registry or load_registry())
    app.include_router(router, prefix="/api/v1", dependencies=[Depends(fake_key)])
    return app


@pytest.fixture
def client():
    return TestClient(make_app(), raise_server_exceptions=False)


def example(name):
    return json.loads((EXAMPLES / name).read_text())


def assert_envelope(resp, status, code=None):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert resp.headers["X-Request-ID"] == body["request_id"]
    if code:
        assert body["error"]["code"] == code
    return body


SENSITIVE = [KEY, str(REPO), "/Users/", "Traceback", 'File "', "site-packages"]


def assert_clean(resp):
    text = resp.text + " ".join(f"{k}: {v}" for k, v in resp.headers.items())
    for bad in SENSITIVE:
        assert bad not in text, bad


# --------------------------------------------------------------------------------------
# Auth and errors
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
@pytest.mark.parametrize(
    "method, path, body",
    [("get", "/api/v1/jurisdictions", None), ("post", "/api/v1/permit-lookups", C01),
     ("post", "/api/v1/locations/resolve", C01["location"]), ("get", "/api/v1/sources/SYN-CITY-GUIDE", None)],
)
def test_401_envelope(client, headers, method, path, body):
    resp = client.request(method, path, json=body, headers=headers)
    assert_envelope(resp, 401, "unauthorized")
    assert_clean(resp)


def test_422_unknown_body_field(client):
    resp = client.post("/api/v1/permit-lookups", json={**C01, "surprise": 1}, headers=HEADERS)
    body = assert_envelope(resp, 422, "validation_error")
    assert body["error"]["details"]["fields"]
    assert "surprise" not in json.dumps(body["error"]["message"])
    resp = client.post("/api/v1/locations/resolve", json={"selected_area": {"jurisdiction": "irvine-ca", "x": 1}}, headers=HEADERS)
    assert_envelope(resp, 422, "validation_error")


def test_422_two_location_modes(client):
    two = {**C01, "location": {"selected_area": {"jurisdiction": "irvine-ca"}, "point": {"lat": 0, "lon": 0}}}
    assert_envelope(client.post("/api/v1/permit-lookups", json=two, headers=HEADERS), 422, "invalid_location_input")
    resp = client.post("/api/v1/locations/resolve", json=two["location"], headers=HEADERS)
    assert_envelope(resp, 422, "invalid_location_input")


@pytest.mark.parametrize(
    "facts, code",
    [({"adu_form": 5}, "invalid_fact_value"), ({"secret_fact": "SECRET-VALUE"}, "unknown_fact"),
     ({"existing_dwelling": "yes"}, "invalid_fact_value")],
)
def test_422_bad_facts_without_echoing_values(client, facts, code):
    resp = client.post("/api/v1/permit-lookups", json={**C01, "facts": facts}, headers=HEADERS)
    assert_envelope(resp, 422, code)
    assert "SECRET-VALUE" not in resp.text


def test_422_bad_project_type(client):
    assert_envelope(client.post("/api/v1/permit-lookups", json={**C01, "project_type": "castle"}, headers=HEADERS), 422)


def test_strict_types_are_not_coerced(client):
    resp = client.post("/api/v1/permit-lookups", json={**C01, "profile_key": 5}, headers=HEADERS)
    assert_envelope(resp, 422, "validation_error")


def test_request_id_from_request_state():
    c = TestClient(make_app(state_request_id="fixed-request-id"), raise_server_exceptions=False)
    ok = c.post("/api/v1/permit-lookups", json=C01, headers=HEADERS)
    assert ok.json()["request_id"] == "fixed-request-id"
    assert ok.headers["X-Request-ID"] == "fixed-request-id"
    bad = c.get("/api/v1/jurisdictions")
    assert assert_envelope(bad, 401)["request_id"] == "fixed-request-id"


def test_generated_request_ids_are_unique(client):
    a = client.get("/api/v1/jurisdictions", headers=HEADERS).json()["request_id"]
    b = client.get("/api/v1/jurisdictions", headers=HEADERS).json()["request_id"]
    assert a != b and len(a) == 36


def test_internal_error_is_a_clean_500():
    class Broken(InMemoryReleaseProvider):
        def get_active(self, *a):
            raise RuntimeError(f"boom at {REPO}/secret/path with {KEY}")

    base = load_synthetic_provider()
    p = Broken([base.get_active("irvine-ca", "adu", PROFILE)], demo_mode=True)
    c = TestClient(make_app(p), raise_server_exceptions=False)
    resp = c.post("/api/v1/permit-lookups", json=C01, headers=HEADERS)
    assert_envelope(resp, 500, "internal_error")
    assert "boom" not in resp.text
    assert_clean(resp)


# --------------------------------------------------------------------------------------
# Each route matches its example file
# --------------------------------------------------------------------------------------


def test_jurisdictions_matches_example(client):
    resp = client.get("/api/v1/jurisdictions", headers=HEADERS)
    assert resp.status_code == 200
    body, ex = resp.json(), example("jurisdictions.json")["response"]
    assert set(body) == set(ex) - {"example"}
    irvine = next(j for j in body["jurisdictions"] if j["slug"] == "irvine-ca")
    ex_irvine = next(j for j in ex["jurisdictions"] if j["slug"] == "irvine-ca")
    assert set(irvine) == set(ex_irvine)
    assert set(irvine["coverage"][0]) == set(ex_irvine["coverage"][0])
    assert set(irvine["coverage"][0]["release"]) == set(ex_irvine["coverage"][0]["release"])
    assert set(irvine["coverage"][0]["sources"][0]) == set(ex_irvine["coverage"][0]["sources"][0])
    assert irvine["coverage"][0]["profile_key"] == PROFILE
    others = [j for j in body["jurisdictions"] if j["slug"] != "irvine-ca"]
    assert len(others) == 33 and all(j["coverage"] == [] for j in others)
    assert "registry_not_coverage" in [w["code"] for w in body["warnings"]]
    assert_clean(resp)


def test_resolve_matches_example(client):
    ex = example("locations_resolve_selected_area.json")
    resp = client.post("/api/v1/locations/resolve", json=ex["request"]["body"], headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == set(ex["response"]) - {"example"}
    assert body["location"] == ex["response"]["location"]
    assert "selected_area_property_not_verified" in [w["code"] for w in body["warnings"]]


@pytest.mark.parametrize("name", ["permit_lookup_applies.json", "permit_lookup_needs_information.json"])
def test_permit_lookup_matches_example(client, name):
    ex = example(name)["response"]
    resp = client.post("/api/v1/permit-lookups", json=C01, headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == set(ex) - {"example"}
    assert set(body["requirements"][0]) == set(ex["requirements"][0])
    assert set(body["requirements"][0]["citations"][0]) == set(ex["requirements"][0]["citations"][0])
    assert set(body["pathways"][0]) == set(ex["pathways"][0])
    assert set(body["sources_used"][0]) == set(ex["sources_used"][0])
    assert set(body["conflicts"][0]) == set(example("permit_lookup_needs_information.json")["response"]["conflicts"][0])
    assert resp.headers["X-Request-ID"] == body["request_id"]
    assert_clean(resp)


def test_sources_get_matches_example(client):
    ex = example("sources_get.json")["response"]
    resp = client.get("/api/v1/sources/SYN-CITY-GUIDE", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == set(ex) - {"example"}
    assert set(body["source"]) == set(ex["source"])
    assert set(body["source"]["passages"][0]) == set(ex["source"]["passages"][0])
    assert body["source"]["key"] == "SYN-CITY-GUIDE"
    assert body["source"]["url"] == "https://example.org/synthetic/city-guide"
    assert {p["review_status"] for p in body["source"]["passages"]} == {"reviewed"}
    assert_clean(resp)


def test_sources_404(client):
    assert_envelope(client.get("/api/v1/sources/NO-SUCH-SOURCE", headers=HEADERS), 404, "source_not_found")
    resp = client.get("/api/v1/sources/..%2F..%2Fetc%2Fpasswd", headers=HEADERS)
    assert resp.status_code in (404, 422)
    assert_clean(resp)


def test_unreviewed_passages_flagged_on_source(client):
    body = client.get("/api/v1/sources/SYN-STATE-GUIDE", headers=HEADERS).json()
    assert {p["review_status"] for p in body["source"]["passages"]} == {"needs_review"}
    assert "unreviewed_extraction" in [w["code"] for w in body["warnings"]]


# --------------------------------------------------------------------------------------
# Lookup behavior through HTTP
# --------------------------------------------------------------------------------------


def test_c01_floor_area_needs_information(client):
    body = client.post("/api/v1/permit-lookups", json=C01, headers=HEADERS).json()
    reqs = {r["key"]: r for r in body["requirements"]}
    floor = reqs["synthetic_large_unit_document"]
    assert floor["status"] == "needs_information"
    assert floor["missing_fact_keys"] == ["floor_area_sqft"]
    assert reqs["synthetic_conflicted_checklist"]["status_reason"] == "source_conflict"
    assert reqs["synthetic_application_form"]["status"] == "applies"
    for r in body["requirements"]:
        assert r["citations"]
        if r["status"] == "not_applicable":
            assert r["missing_fact_keys"] == []
    assert body["status"] == "needs_information"
    assert body["dataset_mode"] == "synthetic"
    assert "synthetic_dataset" in [w["code"] for w in body["warnings"]]


def test_sources_used_lists_each_cited_source_once(client):
    body = client.post("/api/v1/permit-lookups", json=C01, headers=HEADERS).json()
    used = [s["source_key"] for s in body["sources_used"]]
    cited = [c["source_key"] for item in body["pathways"] + body["requirements"] for c in item["citations"]]
    assert sorted(used) == sorted(set(cited))
    assert len(used) == len(set(used))
    assert set(body["sources_used"][0]) == {"source_key", "title", "url", "publisher", "checked_at", "verification_depth"}


def test_multifamily_rule_coverage_unavailable(client):
    resp = client.post("/api/v1/permit-lookups", json={**C01, "project_type": "multifamily", "facts": {}}, headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rule_coverage_unavailable"
    assert body["requirements"] == [] and body["sources_used"] == []


def test_dataset_unavailable_is_503_envelope():
    p = InMemoryReleaseProvider((), demo_mode=True, configured=[CoverageEntry("irvine-ca", "adu", PROFILE)])
    c = TestClient(make_app(p), raise_server_exceptions=False)
    assert_envelope(c.post("/api/v1/permit-lookups", json=C01, headers=HEADERS), 503, "dataset_unavailable")


def test_router_has_no_prefix_of_its_own():
    router = build_lookup_router(load_synthetic_provider(), [Jurisdiction("irvine-ca", "Irvine")])
    paths = {r.path for r in router.routes}
    assert paths == {"/jurisdictions", "/locations/resolve", "/permit-lookups", "/sources/{source_key}"}


# --------------------------------------------------------------------------------------
# Dev server
# --------------------------------------------------------------------------------------


def test_dev_server_refuses_to_start_without_key():
    for env in ({}, {"CLEARPATH_API_KEY": ""}, {"CLEARPATH_API_KEY": "   "}):
        with pytest.raises(DevServerConfigError):
            build_from_env([], env)


def test_dev_server_app_auth_health_and_cors():
    app, banner = build_from_env([], {"CLEARPATH_API_KEY": KEY, "CLEARPATH_CORS_ORIGINS": "http://localhost:5173, http://127.0.0.1:5173"})
    assert KEY not in banner
    assert "SYNTHETIC" in banner
    c = TestClient(app, raise_server_exceptions=False)
    assert c.get("/health/live").json() == {"status": "ok"}
    assert_envelope(c.get("/api/v1/jurisdictions"), 401, "unauthorized")
    ok = c.post("/api/v1/permit-lookups", json=C01, headers=HEADERS)
    assert ok.status_code == 200 and ok.headers["X-Request-ID"] == ok.json()["request_id"]
    pre = c.options("/api/v1/permit-lookups", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-API-Key, Content-Type"})
    assert pre.headers.get("access-control-allow-origin") == "http://localhost:5173"
    other = c.get("/health/live", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers
    assert_envelope(c.get("/api/v1/nope", headers=HEADERS), 404)


def test_dev_server_no_cors_by_default():
    app, _ = build_from_env([], {"CLEARPATH_API_KEY": KEY})
    c = TestClient(app)
    resp = c.get("/health/live", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in resp.headers


def test_dev_server_real_draft_is_flagged_test_only():
    real = REPO / "backend" / "data" / "irvine_adu" / "manifest.json"
    if not real.exists():
        pytest.skip("real draft manifest not present")
    before = real.read_bytes()
    app, banner = build_from_env(["--real-draft"], {"CLEARPATH_API_KEY": KEY})
    assert "UNREVIEWED DRAFT" in banner and KEY not in banner
    c = TestClient(app)
    body = c.post("/api/v1/permit-lookups", json=C01, headers=HEADERS).json()
    assert "test_only_unreviewed_release" in [w["code"] for w in body["warnings"]]
    assert body["pathways"][0]["key"] == "irvine_adu_standard"
    assert real.read_bytes() == before
    provider = load_real_draft_provider(real)
    assert provider.get_active("irvine-ca", "adu", None).test_only_unreviewed is True


def test_create_dev_app_requires_key():
    with pytest.raises(DevServerConfigError):
        create_dev_app(load_synthetic_provider(), load_registry(), api_key="", cors_origins=[])
