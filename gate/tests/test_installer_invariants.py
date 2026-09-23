"""Regression guards for the developer installer scripts.

The installer is plain PowerShell/batch/sh, so it is not exercised by unit tests; these assertions lock in the
invariants that matter for security and for the "share the repo and install" flow, and fail in CI if a future edit
re-introduces the bundled-credential path or the WSL shell-injection surface that were removed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

CLIENT = Path(__file__).resolve().parents[2] / "client"


def _read(name: str) -> str:
    return (CLIENT / name).read_text(encoding="utf-8")


def test_bundled_credential_machinery_is_gone():
    # The credential-bundle and dependency-bootstrap scripts must not come back.
    assert not (CLIENT / "make-bundle.ps1").exists()
    assert not (CLIENT / "bootstrap.ps1").exists()
    for launcher in ("install.cmd", "install.command", "install.ps1"):
        text = _read(launcher)
        assert "gate.record" not in text, f"{launcher} still references a bundled credential file"
        assert "AI_SDLC_GATE_RECORD_FILE" not in text, f"{launcher} still wires the bundled-record env var"
        assert "import-record" not in text, f"{launcher} still imports a bundled record instead of using the broker"


def test_install_ps1_uses_the_broker_configure():
    ps1 = _read("install.ps1")
    assert "Gate configure --config $config" in ps1, "install.ps1 must configure via the central broker"
    assert "requires Python 3.10" not in ps1.lower() or "3.10" in ps1  # sanity: the version check exists
    assert "(3,10)" in ps1, "install.ps1 must accept Python 3.10+"


def test_no_wsl_shell_command_injection_surface():
    # The Windows installer must not build a bash command from a WSL distribution name / path (the old injection
    # vector). Provisioning WSL from Windows was removed; WSL users run install.sh inside WSL instead.
    ps1 = _read("install.ps1")
    assert "wsl.exe -d" not in ps1, "install.ps1 must not run commands inside WSL distributions"
    assert "bash -lc" not in ps1, "install.ps1 must not construct an inline bash command for WSL"
    assert "handover.json" not in ps1, "install.ps1 must not export a credential handover file"


def test_git_operations_have_a_network_timeout():
    ps1 = _read("install.ps1")
    assert "http.lowSpeedLimit" in ps1 and "http.lowSpeedTime" in ps1, "git clone/fetch should abort on a stalled network"


def test_installer_does_not_set_a_persistent_git_config_parameters_override():
    # GIT_CONFIG_PARAMETERS outranks the git config file and lingers in open shells; a stale value from an earlier
    # install breaks git until every terminal restarts. The installer must rely on global core.hooksPath and only
    # CLEAR a stale override, never set a new persistent one.
    ps1 = _read("install.ps1")
    assert 'core.hooksPath=$hooksPosix' not in ps1  # the old "set GIT_CONFIG_PARAMETERS to a value" pattern is gone
    assert "SetEnvironmentVariable(\"GIT_CONFIG_PARAMETERS\", $null" in ps1  # only clears it
    assert "git config --global core.hooksPath" in ps1

    sh = _read("install.sh")
    assert "export GIT_CONFIG_PARAMETERS=" not in sh, "install.sh must not export a persistent override"
    assert 'git config --global core.hooksPath "$SDLC_HOME/hooks"' in sh


@pytest.mark.parametrize("launcher,script", [("install.cmd", "install.ps1"), ("install.command", "install.sh")])
def test_launchers_clone_when_the_local_script_is_absent(launcher, script):
    text = _read(launcher)
    assert script in text, f"{launcher} should run {script} when present locally"
    assert "git clone" in text, f"{launcher} should clone the repository when {script} is not local"
    assert "arijitaich-og1o/ai-sdlc-gate" in text
