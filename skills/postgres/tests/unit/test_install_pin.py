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
