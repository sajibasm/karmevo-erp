import pytest
from fastapi.testclient import TestClient
from support import TEST_ISSUER, bearer

from erp.app import ApplicationFactory
from erp.modules.platform.models import Company
from erp.modules.platform.registry_models import Identity, Membership


@pytest.fixture
def client(registry, router, verifier):
    factory = ApplicationFactory(registry=registry, tenant_router=router, verifier=verifier)
    return TestClient(factory.build())


@pytest.fixture
def people(registry, two_tenants):
    """alice: A · bob: A and B · carol: none · dave: suspended in A."""
    ids = {}
    for name in ("alice", "bob", "carol", "dave"):
        with registry.platform_session() as s:
            identity = Identity(issuer=TEST_ISSUER, subject=name)
            s.add(identity)
            s.flush()
            ids[name] = identity.identity_id

    def member(tenant_id, name, status="active"):
        with registry.tenant_session(tenant_id) as s:
            s.add(
                Membership(
                    tenant_id=tenant_id,
                    identity_id=ids[name],
                    membership_status=status,
                )
            )

    member(two_tenants.a, "alice")
    member(two_tenants.a, "bob")
    member(two_tenants.b, "bob")
    member(two_tenants.a, "dave", status="suspended")
    return ids


def _companies(client, token, tenant_id=None, query=""):
    headers = bearer(token)
    if tenant_id is not None:
        headers["X-Tenant-Id"] = str(tenant_id)
    return client.get(f"/api/v1/companies{query}", headers=headers)


def _names(response):
    return [c["companyName"] for c in response.json()["items"]]


def test_missing_token_is_401_problem(client):
    response = client.get("/api/v1/companies")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_401(client):
    response = client.get("/api/v1/companies", headers=bearer("garbage"))

    assert response.status_code == 401


def test_unprovisioned_identity_is_403(client, make_token, people):
    response = _companies(client, make_token("mallory"))

    assert response.status_code == 403
    assert response.json()["code"] == "IDENTITY_NOT_PROVISIONED"


def test_single_membership_selects_tenant_automatically(client, make_token, people):
    response = _companies(client, make_token("alice"))

    assert response.status_code == 200
    assert _names(response) == ["Alpha Traders Ltd"]
    assert response.json()["nextCursor"] is None


def test_response_keys_are_camel_case(client, make_token, people):
    company = _companies(client, make_token("alice")).json()["items"][0]

    expected = {"companyId", "companyName", "countryCode", "baseCurrency", "timeZone"}
    assert set(company) == expected


def test_selecting_a_tenant_without_membership_is_denied(client, make_token, people, two_tenants):
    response = _companies(client, make_token("alice"), tenant_id=two_tenants.b)

    assert response.status_code == 403
    assert response.json()["code"] == "TENANT_ACCESS_DENIED"


def test_multi_tenant_user_must_select_then_reads_that_database(
    client, make_token, people, two_tenants
):
    token = make_token("bob")

    unselected = _companies(client, token)
    selected = _companies(client, token, tenant_id=two_tenants.b)

    assert unselected.status_code == 400
    assert unselected.json()["code"] == "TENANT_SELECTION_REQUIRED"
    assert _names(selected) == ["Beta Foods Ltd"]


@pytest.mark.parametrize("subject", ["carol", "dave"], ids=["no-membership", "suspended"])
def test_users_without_active_membership_are_denied(client, make_token, people, subject):
    response = _companies(client, make_token(subject))

    assert response.status_code == 403
    assert response.json()["code"] == "TENANT_ACCESS_DENIED"


def test_me_contexts_lists_only_active_memberships(client, make_token, people):
    headers = bearer(make_token("bob"))

    response = client.get("/api/v1/me/contexts", headers=headers)

    assert response.status_code == 200
    numbers = [c["accountNumber"] for c in response.json()]
    assert numbers == ["100001", "100002"]


def test_companies_pagination_uses_cursor(client, make_token, people, router, two_tenants):
    a = two_tenants.a
    with router.for_tenant(a).tenant_session(a) as s:
        s.add(
            Company(
                tenant_id=a,
                company_name="Alpha Retail Ltd",
                country_code="BD",
                base_currency="BDT",
                time_zone="Asia/Dhaka",
            )
        )
    token = make_token("alice")

    first = _companies(client, token, query="?limit=1").json()
    cursor = first["nextCursor"]
    second = _companies(client, token, query=f"?limit=1&cursor={cursor}").json()

    assert len(first["items"]) == 1 and cursor is not None
    assert len(second["items"]) == 1 and second["nextCursor"] is None
    first_id = first["items"][0]["companyId"]
    assert first_id != second["items"][0]["companyId"]
