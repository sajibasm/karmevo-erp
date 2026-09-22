from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

LEAK_CHECK = "select pg_backend_pid(), nullif(current_setting('{name}', true), '')"


def test_runtime_role_is_not_superuser_and_cannot_bypass_rls(registry):
    with registry.platform_session() as s:
        row = s.execute(
            text("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        ).one()
    assert (row.rolsuper, row.rolbypassrls) == (False, False)


def test_runtime_role_cannot_run_ddl(registry):
    with pytest.raises(DBAPIError, match="permission denied"):
        with registry.platform_session() as s:
            s.execute(text('create table registry."ShouldNotExist" ("value" int)'))


def test_tenant_context_is_visible_inside_its_transaction(registry):
    tenant_id = uuid4()
    with registry.tenant_session(tenant_id) as s:
        value = s.execute(text("select current_setting('app.tenant_id')")).scalar_one()
    assert value == str(tenant_id)


def test_tenant_context_does_not_leak_on_the_same_connection(
    single_connection_registry,
):
    with single_connection_registry.tenant_session(uuid4()) as s:
        first_pid = s.execute(text("select pg_backend_pid()")).scalar_one()
    with single_connection_registry.platform_session() as s:
        check = text(LEAK_CHECK.format(name="app.tenant_id"))
        pid, leaked = s.execute(check).one()
    assert pid == first_pid
    assert leaked is None


def test_tenant_context_is_cleared_after_rollback(single_connection_registry):
    with pytest.raises(RuntimeError):
        with single_connection_registry.tenant_session(uuid4()):
            raise RuntimeError("business rule failed")
    with single_connection_registry.platform_session() as s:
        check = text(LEAK_CHECK.format(name="app.tenant_id"))
        _, leaked = s.execute(check).one()
    assert leaked is None


def test_identity_context_is_transaction_local(single_connection_registry):
    identity_id = uuid4()
    database = single_connection_registry
    with database.platform_session(identity_id=identity_id) as s:
        inside = s.execute(text("select current_setting('app.identity_id')")).scalar_one()
    with database.platform_session() as s:
        check = text(LEAK_CHECK.format(name="app.identity_id"))
        _, leaked = s.execute(check).one()
    assert inside == str(identity_id)
    assert leaked is None
