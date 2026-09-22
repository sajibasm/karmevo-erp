from typing import ClassVar

from erp.core.modules import ModuleCatalog, ModuleManifest
from erp.modules.integration.module import MODULE as INTEGRATION
from erp.modules.platform.module import MODULE as PLATFORM


class InstalledModules:
    """Modules installed in this build; register each MODULE here."""

    MANIFESTS: ClassVar[tuple[ModuleManifest, ...]] = (PLATFORM, INTEGRATION)

    @classmethod
    def catalog(cls) -> ModuleCatalog:
        return ModuleCatalog(cls.MANIFESTS)
