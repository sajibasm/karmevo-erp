"""Shared fixtures.

Database tests need the dev stack:
docker compose -f deploy/compose.dev.yml up -d --wait
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from erp.core.db import Database

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
