# 0011 — Class-based (object-oriented) code structure

**Status:** Accepted 2026-09-22 (owner: "need to be object oriented, class based"; strict, with repositories) · Extends ADR-0009 (module layout) and ADR-0010 (PEP 8)

## Decision
Each module is built from classes with one responsibility each. Collaborators are passed in through `__init__` (constructor injection), never imported as globals.

| File | Class(es) | Responsibility |
|---|---|---|
| `models.py` | SQLAlchemy model classes (`Company`) | Table mapping only |
| `schemas.py` | Pydantic classes (`CompanyOut`, `CompanyPage`) | API input/output shapes |
| `repository.py` | `CompanyRepository(session)` | All queries for one aggregate; no business rules, no commits |
| `service.py` | `CompanyService(tenant_db, …)` | Business rules; opens the transaction (`tenant_session`), uses repositories, writes audit/outbox |
| `controller.py` | `CompanyController(Controller)` | HTTP only: parse, authorize, call the service, map errors. Owns an `APIRouter` and registers its methods as routes |
| `config.py` | `SalesConfig(ModuleConfig)` | Module settings model |
| `module.py` | `MODULE = ModuleManifest(...)` (a declarative object, not a function) | Manifest: key, dependencies, core flag, `Controller` classes |
| `interface.py` | Facade class (`SalesFacade`) or re-exported service classes | The only surface other modules use |
| `utils.py` | Small helper classes | Module-private helpers |

`core` infrastructure is already class-based: `Database`, `TenantDbLocator`, `TenantDatabaseRouter`, `TokenVerifier`, `TenantProvisioner`, `ModuleCatalog`, `TenantModules`, `OutboxRelay`.

### Controller pattern (FastAPI has no built-in class-based views)

```python
class Controller:
    """Base: subclasses register bound methods on their own router."""

    prefix: str = ""
    tags: tuple[str, ...] = ()

    def __init__(self) -> None:
        self.router = APIRouter(prefix=self.prefix, tags=list(self.tags))
        self.register_routes()

    def register_routes(self) -> None:
        raise NotImplementedError


class CompanyController(Controller):
    prefix = "/api/v1/companies"
    tags = ("platform",)

    def register_routes(self) -> None:
        self.router.add_api_route("", self.list_companies, methods=["GET"])

    def list_companies(
        self,
        service: Annotated[CompanyService, Depends(CompanyService.provide)],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        cursor: UUID | None = None,
    ) -> CompanyPage:
        return service.list_page(limit=limit, cursor=cursor)
```

Services expose a `provide` classmethod that FastAPI uses as the per-request dependency. It builds the service from the request's tenant context and database, which keeps controllers free of wiring.

## Owner decisions (2026-09-22)
1. **Everything in classes.** There are no module-level functions in `erp/`. Stateless helpers become `@staticmethod`s or `@classmethod`s on a named class, e.g. `Money.quantize(...)`, `RlsSql.tenant_policy(...)`, `SqlIdentifier.safe(...)`.
   Exceptions that Python or tooling require:
   - Alembic migration files keep their mandatory module-level `upgrade()`/`downgrade()` functions; they may call helper classes.
   - The `if __name__ == "__main__":` entry line calls `Cli().run()`.
   - FastAPI `Depends` providers are classmethods (e.g. `CompanyService.provide`).
   - Tests may use plain pytest functions and fixtures. Pytest's function style is not application code, and test classes are optional.
2. **Repository layer: yes.** Controller → Service → Repository → Model. Repositories hold every query for their aggregate. Services never build queries directly.

## Consequences
- More files and boilerplate per module, in exchange for clear seams for testing (fake repositories and services) and a uniform structure across all 50 apps.
- FastAPI dependency injection still works: controller methods declare `Depends(...)` parameters; bound methods are registered with `add_api_route`.
