"""install_odoo.sh refuses a box too SMALL to hold the stack — and only that.

The bar is memory and disk, never the substrate: measured on a live install the whole stack
is ~1.0 GB and 2.0 GB on disk, so a Power container (3 GB / 20 GB) holds it comfortably and
this recipe was proven under gVisor from the start. The gate reads OTENY_MEM_GB (the deployer
injects it from the tenant's envelope; /proc + cgroup v2 are the fallbacks) and refuses only
Lite-class boxes, with a "upgrade to Power or Max" message and NO install work done.
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


def test_a_container_substrate_is_no_longer_refused(tmp_path):
    """The substrate ban is gone: a Power container fits the stack with room to spare, so
    the only question is how big the box is. A container with Power memory must PASS the
    envelope gate (it fails later, offline, on the Odoo download — out of scope here)."""
    r = _run({"OTENY_SUBSTRATE": "container", "OTENY_MEM_GB": "3"}, tmp_path)
    assert "ODOO_INSTALL_REFUSED mem=" not in r.stderr
    assert "substrate=container" not in r.stderr


def test_refuses_a_lite_class_box(tmp_path):
    r = _run({"OTENY_SUBSTRATE": "container", "OTENY_MEM_GB": "1.5"}, tmp_path)
    assert r.returncode == 1
    assert "ODOO_INSTALL_REFUSED mem=" in r.stderr
    assert "Power or Max" in r.stderr
    assert not (tmp_path / "odoo-site").exists()


def test_the_power_envelope_is_allowed(tmp_path):
    """The measurement that moved the floor: Power is 3072 MB and the stack needs ~1 GB.
    The old 3.2 GiB floor missed Power by 205 MB and cost the whole tier the capability."""
    r = _run({"OTENY_MEM_GB": "3"}, tmp_path)
    assert "ODOO_INSTALL_REFUSED mem=" not in r.stderr
    # …and the floor still bites just below it.
    r = _run({"OTENY_MEM_GB": "1.9"}, tmp_path)
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
