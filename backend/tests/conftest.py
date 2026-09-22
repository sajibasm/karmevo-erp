"""Shared fixtures.

Database tests need the dev stack:
docker compose -f deploy/compose.dev.yml up -d --wait
"""

import json
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.pool import NullPool
from support import APP, OWNER, RELAY, TEST_AUDIENCE, TEST_ISSUER

from erp.core.db import Database, TenantDbLocator
from erp.core.security import TokenVerifier
from erp.modules.platform.models import Company
from erp.modules.platform.provisioning import TenantProvisioner
from erp.modules.platform.tenant_db import TenantDatabaseRouter

BACKEND_DIR = Path(__file__).resolve().parents[1]
REGISTRY_APP_URL = os.environ.get(
    "ERP_TEST_REGISTRY_URL",
    "postgresql+psycopg://erp_app:erp_app_dev@localhost:55432/erp_registry_test",
)
REGISTRY_OWNER_URL = os.environ.get(
    "ERP_TEST_REGISTRY_MIGRATION_URL",
    "postgresql+psycopg://erp_owner:erp_owner_dev@localhost:55432/erp_registry_test",
)


def truncate_tables(engine: Engine, *, exclude: frozenset[str] = frozenset()) -> None:
    """Empty every application table except `exclude`.

    Names in `exclude` are quoted, e.g. 'registry."Tenants"'.
    """
    with engine.begin() as conn:
        tables = (
            conn.execute(
                text(
                    "select quote_ident(schemaname) || '.' || quote_ident(tablename) "
                    "from pg_tables where schemaname not in "
                    "('pg_catalog', 'information_schema', 'public')"
                )
            )
            .scalars()
            .all()
        )
        targets = [t for t in tables if t not in exclude]
        if targets:
            conn.execute(text(f"TRUNCATE {', '.join(targets)} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def registry_owner_engine() -> Iterator[Engine]:
    """Migrate erp_registry_test from scratch once per run.

    Starting with a downgrade also exercises every downgrade path.
    """
    cfg = Config(str(BACKEND_DIR / "alembic.ini"), ini_section="registry")
    cfg.set_main_option("sqlalchemy.url", REGISTRY_OWNER_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(REGISTRY_OWNER_URL)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def _registry(registry_owner_engine: Engine) -> Iterator[Database]:
    database = Database(REGISTRY_APP_URL)
    yield database
    database.dispose()


@pytest.fixture
def registry(_registry: Database, registry_owner_engine: Engine) -> Iterator[Database]:
    """Registry DB as erp_app; emptied after each test.

    "Tenants" rows are kept because session fixtures provision tenant
    databases for them.
    """
    yield _registry
    truncate_tables(registry_owner_engine, exclude=frozenset({'registry."Tenants"'}))


@pytest.fixture
def single_connection_registry(
    registry_owner_engine: Engine,
) -> Iterator[Database]:
    """A one-connection pool, to prove context never leaks."""
    database = Database(REGISTRY_APP_URL, pool_size=1, max_overflow=0)
    yield database
    database.dispose()


TENANT_DB_SERVERS = {"default": os.environ.get("ERP_TEST_TENANT_DB_SERVER", "localhost:55432")}
TENANT_DB_PREFIX = "erp_test_t_"


@pytest.fixture(scope="session")
def locator() -> TenantDbLocator:
    return TenantDbLocator(TENANT_DB_SERVERS, database_prefix=TENANT_DB_PREFIX)


def _server_admin(locator: TenantDbLocator) -> Engine:
    return create_engine(
        locator.url("default", "postgres", OWNER),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )


def _drop_test_tenant_databases(locator: TenantDbLocator) -> None:
    engine = _server_admin(locator)
    pattern = TENANT_DB_PREFIX.replace("_", r"\_") + "%"
    with engine.connect() as conn:
        names = (
            conn.execute(
                text("select datname from pg_database where datname like :pattern"),
                {"pattern": pattern},
            )
            .scalars()
            .all()
        )
        for name in names:
            conn.execute(text(f'DROP DATABASE "{name}"'))
    engine.dispose()


@pytest.fixture(scope="session")
def provisioner(_registry: Database, locator: TenantDbLocator) -> Iterator[TenantProvisioner]:
    """Provision real erp_test_t_* databases; dropped at session end."""
    _drop_test_tenant_databases(locator)  # leftovers from aborted runs
    yield TenantProvisioner.create(
        _registry,
        locator,
        owner=OWNER,
        runtime_roles=["erp_app", "erp_relay"],
        alembic_ini=BACKEND_DIR / "alembic.ini",
    )
    _drop_test_tenant_databases(locator)


@pytest.fixture(scope="session")
def owner_connect(locator: TenantDbLocator):
    @contextmanager
    def _connect(database: str) -> Iterator[Connection]:
        url = locator.url("default", database, OWNER)
        engine = create_engine(url, poolclass=NullPool)
        try:
            with engine.begin() as conn:
                yield conn
        finally:
            engine.dispose()

    return _connect


@pytest.fixture(scope="session")
def drop_database(locator: TenantDbLocator):
    def _drop(name: str) -> None:
        engine = _server_admin(locator)
        with engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}"'))
        engine.dispose()

    return _drop


@pytest.fixture(scope="session")
def router(
    _registry: Database,
    locator: TenantDbLocator,
    provisioner: TenantProvisioner,
) -> Iterator[TenantDatabaseRouter]:
    tenant_router = TenantDatabaseRouter(_registry, locator, APP)
    yield tenant_router
    tenant_router.dispose_all()  # before the databases are dropped


@pytest.fixture(scope="session")
def relay_router(
    _registry: Database,
    locator: TenantDbLocator,
    provisioner: TenantProvisioner,
) -> Iterator[TenantDatabaseRouter]:
    """Tenant DBs as erp_relay: access to "OutboxEvents" only."""
    relay = TenantDatabaseRouter(_registry, locator, RELAY)
    yield relay
    relay.dispose_all()


@pytest.fixture(scope="session")
def provisioned(provisioner: TenantProvisioner) -> tuple[UUID, UUID]:
    """Tenants A (100001) and B (100002), each with its own database."""
    a = provisioner.provision(account_number="100001", tenant_name="Alpha Traders")
    b = provisioner.provision(account_number="100002", tenant_name="Beta Foods")
    return a, b


@dataclass(frozen=True)
class SeededTenants:
    a: UUID
    b: UUID
    company_a: UUID
    company_b: UUID


@pytest.fixture
def two_tenants(provisioned, router, locator, registry) -> Iterator[SeededTenants]:
    """One company per tenant, written as erp_app; emptied after."""
    a, b = provisioned
    names = ("Alpha Traders Ltd", "Beta Foods Ltd")
    company_ids = []
    for tenant_id, name in zip((a, b), names, strict=True):
        with router.for_tenant(tenant_id).tenant_session(tenant_id) as s:
            company = Company(
                tenant_id=tenant_id,
                company_name=name,
                country_code="BD",
                base_currency="BDT",
                time_zone="Asia/Dhaka",
            )
            s.add(company)
            s.flush()
            company_ids.append(company.company_id)
    yield SeededTenants(a, b, company_ids[0], company_ids[1])
    for tenant_id in (a, b):
        url = locator.url("default", locator.database_name(tenant_id), OWNER)
        engine = create_engine(url, poolclass=NullPool)
        truncate_tables(engine, exclude=frozenset({'platform."DatabaseOwners"'}))
        engine.dispose()


@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def verifier(signing_key: rsa.RSAPrivateKey) -> TokenVerifier:
    public_key = signing_key.public_key()
    return TokenVerifier(
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        algorithms=["RS256"],
        key_resolver=lambda _token: public_key,
    )


@pytest.fixture(scope="session")
def make_token(signing_key: rsa.RSAPrivateKey) -> Callable[..., str]:
    def _make(
        subject: str | None = "alice",
        *,
        issuer: str = TEST_ISSUER,
        audience: str = TEST_AUDIENCE,
        expires_in: int = 300,
        algorithm: str = "RS256",
        key: object | None = None,
        **extra: object,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "iat": now,
            "exp": now + expires_in,
            **extra,
        }
        if subject is None:
            del claims["sub"]
        return jwt.encode(claims, key or signing_key, algorithm=algorithm)

    return _make


@pytest.fixture
def cli_env(monkeypatch):
    """Point erp.cli at the test registry and tenant-DB prefix."""
    from erp.core.config import Settings

    monkeypatch.setenv("ERP_REGISTRY_DATABASE_URL", REGISTRY_APP_URL)
    monkeypatch.setenv("ERP_TENANT_DB_PREFIX", TENANT_DB_PREFIX)
    monkeypatch.setenv("ERP_TENANT_DB_SERVERS", json.dumps(TENANT_DB_SERVERS))
    Settings.load.cache_clear()
    yield
    Settings.load.cache_clear()
