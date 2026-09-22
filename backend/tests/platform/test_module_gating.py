from fastapi.testclient import TestClient
from support import TEST_ISSUER, bearer

from erp.app import ApplicationFactory
from erp.core.controller import Controller
from erp.core.modules import ModuleCatalog, ModuleManifest
from erp.module_catalog import InstalledModules
from erp.modules.platform.registry_models import Identity, Membership


class DemoController(Controller):
    prefix = "/api/v1/demo"
    tags = ("demo",)

    def register_routes(self) -> None:
        self.router.add_api_route("/ping", self.ping, methods=["GET"])

    def ping(self) -> dict[str, bool]:
        return {"pong": True}


def test_every_route_of_a_disabled_module_is_rejected(
    registry, router, verifier, make_token, two_tenants
):
    demo = ModuleManifest("demo", "Demo", ("platform",), controllers=(DemoController,))
    catalog = ModuleCatalog([*InstalledModules.MANIFESTS, demo])
    app = ApplicationFactory(
        registry=registry, tenant_router=router, verifier=verifier, catalog=catalog
    ).build()
    client = TestClient(app)
    with registry.platform_session() as s:
        identity = Identity(issuer=TEST_ISSUER, subject="alice")
        s.add(identity)
        s.flush()
        identity_id = identity.identity_id
    with registry.tenant_session(two_tenants.a) as s:
        s.add(Membership(tenant_id=two_tenants.a, identity_id=identity_id))
    headers = bearer(make_token("alice"))
    modules = app.state.tenant_modules

    disabled = client.get("/api/v1/demo/ping", headers=headers)
    modules.enable(two_tenants.a, "demo")
    enabled = client.get("/api/v1/demo/ping", headers=headers)
    modules.disable(two_tenants.a, "demo")
    disabled_again = client.get("/api/v1/demo/ping", headers=headers)

    assert disabled.status_code == 403
    assert disabled.json()["code"] == "MODULE_DISABLED"
    assert enabled.json() == {"pong": True}
    assert disabled_again.status_code == 403
