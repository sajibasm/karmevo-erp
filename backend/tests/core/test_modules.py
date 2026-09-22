import pytest

from erp.core.modules import ModuleCatalog, ModuleCatalogError, ModuleManifest


def manifest(key, depends_on=(), core=False):
    return ModuleManifest(key, key.title(), tuple(depends_on), core)


CATALOG = ModuleCatalog(
    [
        manifest("platform", core=True),
        manifest("catalog", ["platform"]),
        manifest("inventory", ["catalog"]),
        manifest("sales", ["inventory", "catalog"]),
        manifest("pos", ["sales"]),
    ]
)


def test_iteration_follows_enable_order():
    keys = [m.key for m in CATALOG]

    assert keys == ["platform", "catalog", "inventory", "sales", "pos"]


def test_dependencies_are_transitive_and_in_enable_order():
    expected = ["platform", "catalog", "inventory", "sales"]
    assert CATALOG.dependencies("pos") == expected


def test_dependents_are_transitive():
    assert CATALOG.dependents("inventory") == ["sales", "pos"]


def test_unknown_dependency_is_rejected():
    with pytest.raises(ModuleCatalogError, match="unknown module 'inventory'"):
        ModuleCatalog([manifest("sales", ["inventory"])])


def test_dependency_cycle_is_rejected():
    with pytest.raises(ModuleCatalogError, match="cycle"):
        ModuleCatalog([manifest("a", ["b"]), manifest("b", ["a"])])


def test_duplicate_key_is_rejected():
    with pytest.raises(ModuleCatalogError, match="duplicate"):
        ModuleCatalog([manifest("a"), manifest("a")])


def test_core_module_cannot_depend_on_an_optional_module():
    with pytest.raises(ModuleCatalogError, match="core module"):
        ModuleCatalog([manifest("sales"), manifest("platform", ["sales"], core=True)])
