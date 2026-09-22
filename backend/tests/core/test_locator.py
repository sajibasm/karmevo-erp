from uuid import UUID

import pytest

from erp.core.db import DbCredentials, TenantDbLocator

LOCATOR = TenantDbLocator({"default": "db.internal:6432"}, database_prefix="erp_t_")


def test_database_name_is_prefix_plus_uuid_hex():
    tenant_id = UUID("0190f1c2-0000-7000-8000-000000000001")

    expected = "erp_t_0190f1c2000070008000000000000001"
    assert LOCATOR.database_name(tenant_id) == expected


def test_url_uses_server_address_and_escapes_credentials():
    credentials = DbCredentials("erp_app", "p@ss:w/rd")

    url = LOCATOR.url("default", "erp_t_x", credentials)

    assert (url.host, url.port, url.database) == ("db.internal", 6432, "erp_t_x")
    assert url.password == "p@ss:w/rd"
    assert "p%40ss" in url.render_as_string(hide_password=False)


def test_unknown_server_is_rejected():
    with pytest.raises(ValueError, match="unknown tenant database server"):
        LOCATOR.url("eu-2", "erp_t_x", DbCredentials("erp_app", "x"))


@pytest.mark.parametrize("prefix", ["", "Erp_", "erp-t-", "x;drop"])
def test_unsafe_prefixes_are_rejected(prefix):
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        TenantDbLocator({"default": "db:5432"}, database_prefix=prefix)
