from erp.core.modules import ModuleManifest

MODULE = ModuleManifest(key="integration", name="Integration", depends_on=("platform",), core=True)
