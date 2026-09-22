from erp.main import ProductionApp


def test_build_wires_registry_router_verifier_and_modules():
    app = ProductionApp.build()

    assert app.state.registry is not None
    assert app.state.tenant_router is not None
    assert app.state.verifier is not None
    assert app.state.tenant_modules is not None
