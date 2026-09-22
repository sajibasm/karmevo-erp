from erp.core.modules import ModuleManifest
from erp.modules.platform.controller import CompanyController, MeController

MODULE = ModuleManifest(
    key="platform",
    name="Platform",
    core=True,
    controllers=(MeController, CompanyController),
)
