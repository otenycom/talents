"""Carried Postgres clusters pin en_US.UTF-8; containers often lack that locale.

Read `REAL_CONF` below before touching anything here. Every fixture in the first version
of this file wrote `lc_messages = 'en_US.UTF-8'` and stopped at the quote — a line shape
Postgres never produces. The real file always carries a trailing tab + comment, the regex
anchored `$` straight after the closing quote, so it matched nothing, reported `noop`, and
the whole rewrite was dead on every real cluster. The tests were green the entire time.
A fixture that cannot reproduce the real input is not a test.
"""
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
from normalize_pg_locales import (  # noqa: E402
    normalize_conf, normalize_pgdata, unavailable_lc_values,
)

# Copied VERBATIM off a real carried cluster (hh00412 on node00077, 2026-08-08),
# tabs and comments included. Fixtures for this file come from here, not from memory.
REAL_CONF = (
    "# - Locale and Formatting -\n"
    "datestyle = 'iso, mdy'\n"
    "lc_messages = 'en_US.UTF-8'\t\t# locale for system error message\n"
    "lc_monetary = 'en_US.UTF-8'\t\t# locale for monetary formatting\n"
    "lc_numeric = 'en_US.UTF-8'\t\t# locale for number formatting\n"
    "lc_time = 'en_US.UTF-8'\t\t\t# locale for time formatting\n"
    "default_text_search_config = 'pg_catalog.english'\n"
)
CONTAINER_LOCALES = {"C", "C.utf8", "C.UTF-8", "POSIX"}


def test_rewrites_a_REAL_postgresql_conf_line_with_its_trailing_comment():
    """The live bug: Postgres writes `lc_time = 'en_US.UTF-8'\\t\\t\\t# locale for …`, and the
    rewrite skipped every one of those lines while reporting success."""
    new, changes = normalize_conf(REAL_CONF, CONTAINER_LOCALES)
    assert len(changes) == 4, changes
    assert "en_US.UTF-8" not in new
    assert "lc_messages = 'C.UTF-8'\t\t# locale for system error message" in new
    assert "lc_time = 'C.UTF-8'\t\t\t# locale for time formatting" in new
    # untouched neighbours survive verbatim
    assert "datestyle = 'iso, mdy'" in new
    assert "default_text_search_config = 'pg_catalog.english'" in new


def test_a_conf_the_box_cannot_satisfy_is_reported_not_called_a_noop():
    """`noop` used to mean both "nothing needed" and "I changed nothing and Postgres is
    about to die". Those must not share an outcome."""
    assert unavailable_lc_values(REAL_CONF, CONTAINER_LOCALES) == [
        "lc_messages='en_US.UTF-8'", "lc_monetary='en_US.UTF-8'",
        "lc_numeric='en_US.UTF-8'", "lc_time='en_US.UTF-8'",
    ]
    new, _ = normalize_conf(REAL_CONF, CONTAINER_LOCALES)
    assert unavailable_lc_values(new, CONTAINER_LOCALES) == []


def test_a_vm_that_really_has_en_US_is_left_alone():
    vm_locales = {"C", "C.UTF-8", "en_US.utf8", "en_US.UTF-8"}
    new, changes = normalize_conf(REAL_CONF, vm_locales)
    assert changes == [] and new == REAL_CONF
    assert unavailable_lc_values(REAL_CONF, vm_locales) == []


def test_pgdata_rewrite_fails_loud_when_nothing_usable_exists(tmp_path: Path, monkeypatch):
    """No usable locale at all: we cannot rewrite, so say so instead of returning quietly
    and letting Postgres FATAL a minute later with a less obvious message."""
    pgdata = tmp_path / "pgdata"
    pgdata.mkdir()
    (pgdata / "postgresql.conf").write_text(REAL_CONF)
    monkeypatch.setattr("normalize_pg_locales.available_locales", lambda: set())
    import normalize_pg_locales as npl

    assert npl.main([str(pgdata)]) == 1


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


# ── the half a conf rewrite can never reach ──────────────────────────────────────────── #
def test_the_cluster_is_initialised_with_a_PORTABLE_collation():
    """`lc_*` lives in postgresql.conf and is rewritable; **LC_COLLATE does not.** It is
    baked into pg_database by initdb and cannot be edited afterwards, so a cluster born on
    an Ubuntu VM as en_US.UTF-8 dies on a container with "database locale is incompatible
    with operating system" no matter how well this module rewrites the conf (seen live on
    hh00413). pgserver runs initdb with no --locale, so the environment decides — and it
    must decide C.UTF-8, which every substrate has."""
    ensure = (Path(__file__).resolve().parents[2] / "scripts" / "ensure_site.sh").read_text()
    pgserver_line = next(
        ln for ln in ensure.splitlines()
        if "$VENV/bin/python" in ln and ln.strip().endswith("- <<'PY'"))
    assert "LC_ALL=C.UTF-8" in pgserver_line, pgserver_line
    assert "LANG=C.UTF-8" in pgserver_line, pgserver_line
