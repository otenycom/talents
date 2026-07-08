"""install_odoo.sh refuses an under-provisioned envelope BEFORE any work (§14.2 self-gate).

The gate reads OTENY_SUBSTRATE / OTENY_MEM_GB (the deployer injects them from the tenant's
isolation_tier + envelope; a probe of /proc is the fallback). On a container substrate or a
box under ~3 GB it exits non-zero with an "upgrade to Max" message and does NO install work.
Deterministic + offline (no /proc needed — the env override drives it). Run:

    python3 -m pytest skills/odoo-website/tests/unit/ -q
"""
import os
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install_odoo.sh"


def _run(env, tmp_path):
    return subprocess.run(
        ["sh", str(_SCRIPT)],
        env={**os.environ, "HOME": str(tmp_path), **env},
        capture_output=True, text=True, timeout=60)


def test_refuses_on_a_container_substrate(tmp_path):
    r = _run({"OTENY_SUBSTRATE": "container"}, tmp_path)
    assert r.returncode == 1
    assert "ODOO_INSTALL_REFUSED substrate=container" in r.stderr
    assert "Max plan" in r.stderr
    # it refused BEFORE any install work (no odoo-site dir was created).
    assert not (tmp_path / "odoo-site").exists()


def test_refuses_on_a_too_small_box(tmp_path):
    r = _run({"OTENY_SUBSTRATE": "vm", "OTENY_MEM_GB": "1.5"}, tmp_path)
    assert r.returncode == 1
    assert "ODOO_INSTALL_REFUSED mem=" in r.stderr
    assert "Max plan" in r.stderr
    assert not (tmp_path / "odoo-site").exists()
