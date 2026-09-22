"""Test-only constants and helpers (on pytest's pythonpath)."""

from erp.core.db import DbCredentials

OWNER = DbCredentials("erp_owner", "erp_owner_dev")
APP = DbCredentials("erp_app", "erp_app_dev")
RELAY = DbCredentials("erp_relay", "erp_relay_dev")

TEST_ISSUER = "https://id.test/realms/staff"
TEST_AUDIENCE = "erp-api"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
