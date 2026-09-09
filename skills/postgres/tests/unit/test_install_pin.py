"""The pin is PostgreSQL 18.6.0 on x86_64. Do not drift to 16."""
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install_postgres.sh"
_TEXT = _SCRIPT.read_text(encoding="utf-8")


def test_pin_is_postgres_18_not_16():
    assert "PG_VER=18.6.0" in _TEXT
    assert "16.15" not in _TEXT
    assert "bb3d09f876b2383e25a8c9ce09e32d185a03656a23d074f5195542b1b1b3ca61" in _TEXT


def test_adopts_legacy_pgdata_without_second_initdb():
    assert "LEGACY=$HOME/odoo-site/pgdata" in _TEXT
    assert "POSTGRES_ADOPTED" in _TEXT


def test_ensure_takes_a_lock_so_two_starts_do_not_race():
    ensure = Path(__file__).resolve().parents[2] / "scripts" / "ensure_postgres.sh"
    text = ensure.read_text(encoding="utf-8")
    assert "flock -w 60" in text
    assert "ensure.lock" in text


def test_vendors_libxml2_for_the_sandbox_parent():
    vendor = Path(__file__).resolve().parents[2] / "scripts" / "vendor_pg_runtime_libs.py"
    text = vendor.read_text(encoding="utf-8")
    assert "libxml2_2.9.14+dfsg-1.3ubuntu3.8_amd64.deb" in text
    assert "bfd07c01d6e5ab3e327f3ca5819409b1914bbfb3f1a016d53e4dabd5f96143bb" in text
    assert "c9a70989678660eed9a1e904c74fa043da8bec8e2036856fc16e31ced79b04f8" in text
    assert "vendor_pg_runtime_libs.py" in _TEXT
