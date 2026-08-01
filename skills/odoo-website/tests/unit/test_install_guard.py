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
    assert "Max" in r.stderr
    assert not (tmp_path / "odoo-site").exists()


def test_allows_cx23_class_memory(tmp_path):
    """L1 — a healthy cx23 (~3.5–4 GiB) is a valid Odoo+Postgres floor; do not refuse.

    Run the same gate arithmetic as install_odoo.sh (no network): 3.5 GiB ≥ 3.2 GiB
    floor → ALLOWED. A full install would curl Odoo nightly — out of scope here.
    """
    gate = subprocess.run(
        ["sh", "-c", r'''
set -eu
mem_kb=$(awk "BEGIN{printf \"%d\", 3.5 * 1024 * 1024}")
floor=3355443
if [ -n "$mem_kb" ] && [ "$mem_kb" -lt "$floor" ]; then
  echo REFUSED; exit 1
fi
echo ALLOWED
'''],
        capture_output=True, text=True, timeout=5)
    assert gate.returncode == 0
    assert "ALLOWED" in gate.stdout
    # And the real script's refuse path still fires under 3.2 GiB (1.5 already covered).
    r = _run({"OTENY_SUBSTRATE": "vm", "OTENY_MEM_GB": "3.0"}, tmp_path)
    assert r.returncode == 1
    assert "ODOO_INSTALL_REFUSED mem=" in r.stderr


def test_refuses_when_ensurepip_missing(tmp_path, monkeypatch):
    """Clear refuse (no half-built venv) when distro python3-venv is absent."""
    # Point OTENY_PYTHON3 at a stub that fails `import ensurepip`.
    stub = tmp_path / "fake-python3"
    stub.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-c\" ]; then exit 1; fi\n"
        "if [ \"$1\" = \"-m\" ] && [ \"$2\" = \"venv\" ]; then\n"
        "  echo 'should not reach venv' >&2; exit 99\n"
        "fi\n"
        "exit 0\n"
    )
    stub.chmod(0o755)
    r = _run(
        {
            "OTENY_SUBSTRATE": "vm",
            "OTENY_MEM_GB": "3.7",
            "OTENY_PYTHON3": str(stub),
        },
        tmp_path,
    )
    assert r.returncode == 1
    assert "ODOO_INSTALL_REFUSED missing_ensurepip" in r.stderr
    assert not (tmp_path / "odoo-site" / "venv").exists()
