"""Operator commands; run by the operator, never exposed over HTTP.

    python -m erp.cli provision-tenant --account-number 100001 \\
        --name "Alpha Traders"
    python -m erp.cli upgrade-tenants
    python -m erp.cli enable-module --tenant <uuid> --module sales \\
        --with-dependencies
"""

import argparse
import sys
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from erp.core.config import Settings
from erp.core.db import Database, DbCredentials, TenantDbLocator
from erp.core.errors import DomainError
from erp.core.modules import ModuleCatalogError
from erp.module_catalog import InstalledModules
from erp.modules.platform.module_state import TenantModules
from erp.modules.platform.provisioning import TenantProvisioner


class Cli:
    """Entry point for `python -m erp.cli`."""

    ALEMBIC_INI: ClassVar[Path] = Path(__file__).resolve().parents[2] / "alembic.ini"
    MODULE_COMMANDS: ClassVar[tuple[str, ...]] = (
        "enable-module",
        "disable-module",
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings.load()

    def run(self, argv: list[str] | None = None) -> int:
        args = self._parser().parse_args(argv)
        # erp_app has no write access to registry."Tenants" (I3); the
        # operator CLI runs as erp_owner instead.
        registry = Database(self._settings.registry_migration_database_url)
        try:
            if args.command in self.MODULE_COMMANDS:
                return self._change_module(args, registry)
            provisioner = self._provisioner(registry)
            if args.command == "provision-tenant":
                tenant_id = provisioner.provision(
                    account_number=args.account_number, tenant_name=args.name
                )
                print(tenant_id)
                return 0
            return self._upgrade(provisioner)
        finally:
            registry.dispose()

    @classmethod
    def _parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="erp")
        commands = parser.add_subparsers(dest="command", required=True)
        provision = commands.add_parser(
            "provision-tenant", help="create a tenant and its database"
        )
        provision.add_argument("--account-number", required=True)
        provision.add_argument("--name", required=True)
        commands.add_parser("upgrade-tenants", help="migrate every ready tenant database")
        for name in cls.MODULE_COMMANDS:
            command = commands.add_parser(name)
            command.add_argument("--tenant", required=True, type=UUID)
            command.add_argument("--module", required=True)
            if name == "enable-module":
                command.add_argument("--with-dependencies", action="store_true")
        return parser

    def _provisioner(self, registry: Database) -> TenantProvisioner:
        settings = self._settings
        return TenantProvisioner.create(
            registry,
            TenantDbLocator(
                settings.tenant_db_servers,
                database_prefix=settings.tenant_db_prefix,
            ),
            owner=DbCredentials(settings.tenant_db_owner_user, settings.tenant_db_owner_password),
            runtime_roles=[
                settings.tenant_db_app_user,
                settings.tenant_db_relay_user,
            ],
            alembic_ini=self.ALEMBIC_INI,
        )

    @staticmethod
    def _upgrade(provisioner: TenantProvisioner) -> int:
        outcomes = provisioner.upgrade_all()
        for outcome in outcomes:
            result = outcome.revision or f"FAILED {outcome.error}"
            print(f"{outcome.tenant_id} {result}")
        return 1 if any(o.error for o in outcomes) else 0

    @staticmethod
    def _change_module(args: argparse.Namespace, registry: Database) -> int:
        modules = TenantModules(registry, InstalledModules.catalog())
        try:
            if args.command == "enable-module":
                enabled = modules.enable(
                    args.tenant,
                    args.module,
                    with_dependencies=args.with_dependencies,
                )
                print("enabled: " + (", ".join(enabled) or "nothing new"))
            else:
                modules.disable(args.tenant, args.module)
                print(f"disabled: {args.module}")
        except (DomainError, ModuleCatalogError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0


if __name__ == "__main__":
    sys.exit(Cli().run())
