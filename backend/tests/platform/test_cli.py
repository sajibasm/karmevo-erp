from uuid import UUID, uuid4

from erp.cli import Cli


def test_provision_tenant_prints_the_new_tenant_id(cli_env, provisioner, registry, capsys):
    number = f"C{uuid4().hex[:12]}"
    argv = ["provision-tenant", "--account-number", number, "--name", "Kappa"]

    assert Cli().run(argv) == 0
    UUID(capsys.readouterr().out.strip())


def test_upgrade_tenants_reports_each_ready_tenant(cli_env, provisioned, capsys):
    exit_code = Cli().run(["upgrade-tenants"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert str(provisioned[0]) in output
    assert str(provisioned[1]) in output


def test_enabling_an_unknown_module_fails_cleanly(cli_env, provisioned, registry, capsys):
    argv = ["enable-module", "--tenant", str(provisioned[0]), "--module", "nope"]

    assert Cli().run(argv) == 2
    assert "unknown module" in capsys.readouterr().err
