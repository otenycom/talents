"""Carried Postgres clusters pin en_US.UTF-8; containers often lack that locale."""
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
from normalize_pg_locales import normalize_conf, normalize_pgdata  # noqa: E402


def test_rewrites_missing_locales_to_c_utf8():
    conf = "\n".join([
        "listen_addresses = ''",
        "lc_messages = 'en_US.UTF-8'",
        "lc_monetary = 'en_US.UTF-8'",
        "lc_numeric = 'en_US.UTF-8'",
        "lc_time = 'en_US.UTF-8'",
        "datestyle = 'iso, mdy'",
    ])
    available = {"C", "C.UTF-8", "C.utf8", "POSIX"}
    new, changes = normalize_conf(conf, available)
    assert len(changes) == 4
    assert "lc_messages = 'C.UTF-8'" in new
    assert "lc_monetary = 'C.UTF-8'" in new
    assert "en_US.UTF-8" not in new
    assert "datestyle = 'iso, mdy'" in new


def test_noop_when_locales_are_available():
    conf = "lc_messages = 'en_US.UTF-8'\nlc_time = 'en_US.UTF-8'\n"
    available = {"en_US.UTF-8", "en_US.utf8", "C.UTF-8"}
    new, changes = normalize_conf(conf, available)
    assert changes == []
    assert new == conf


def test_noop_when_already_c_utf8():
    conf = "lc_messages = 'C.UTF-8'\nlc_time = 'C.UTF-8'\n"
    new, changes = normalize_conf(conf, {"C"})
    assert changes == []
    assert new == conf


def test_writes_postgresql_conf_on_disk(tmp_path: Path, monkeypatch):
    pgdata = tmp_path / "pgdata"
    pgdata.mkdir()
    conf = pgdata / "postgresql.conf"
    conf.write_text("lc_messages = 'en_US.UTF-8'\nlc_numeric = 'en_US.UTF-8'\n")
    monkeypatch.setattr(
        "normalize_pg_locales.available_locales",
        lambda: {"C.UTF-8", "C"},
    )
    changes = normalize_pgdata(pgdata)
    assert len(changes) == 2
    text = conf.read_text()
    assert "en_US.UTF-8" not in text
    assert "lc_messages = 'C.UTF-8'" in text


def test_absent_conf_is_noop(tmp_path: Path):
    assert normalize_pgdata(tmp_path / "missing") == []
