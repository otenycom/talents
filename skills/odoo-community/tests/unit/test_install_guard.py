"""install_odoo.sh refuses a box too small. Memory floor, not substrate."""
import os
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install_odoo.sh"


def _run(env, tmp_path):
    # Never fetch Postgres / git in the gate tests.
    merged = {"OTENY_SKIP_STACK": "1", **env}
    return subprocess.run(
        ["sh", str(_SCRIPT)],
        env={**os.environ, "HOME": str(tmp_path), **merged},
        capture_output=True, text=True, timeout=60)


def test_a_container_substrate_is_no_longer_refused(tmp_path):
    r = _run({"OTENY_SUBSTRATE": "container", "OTENY_MEM_GB": "3"}, tmp_path)
    assert "ODOO_INSTALL_REFUSED mem=" not in r.stderr
    assert "substrate=container" not in r.stderr


def test_refuses_a_lite_class_box(tmp_path):
    r = _run({"OTENY_SUBSTRATE": "container", "OTENY_MEM_GB": "1.5"}, tmp_path)
    assert r.returncode == 1
    assert "ODOO_INSTALL_REFUSED mem=" in r.stderr
    assert "Power or Max" in r.stderr
    assert not (tmp_path / "odoo-site" / "odoo").exists()


def test_the_power_envelope_is_allowed(tmp_path):
    r = _run({"OTENY_MEM_GB": "3"}, tmp_path)
    assert "ODOO_INSTALL_REFUSED mem=" not in r.stderr
    r = _run({"OTENY_MEM_GB": "1.9"}, tmp_path)
    assert r.returncode == 1
    assert "ODOO_INSTALL_REFUSED mem=" in r.stderr


def test_refuses_when_ensurepip_missing(tmp_path):
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


def test_recipe_is_shallow_git_not_nightly_zip():
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "git clone --branch 19.0 --single-branch --depth 1 --no-tags" in text
    assert "nightly.odoo.com" not in text
    assert "pgserver" not in text
