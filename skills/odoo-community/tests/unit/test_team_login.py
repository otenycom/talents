"""team_login.py, normalize_login(), admin_login_and_file(), and the
lowercase-logins migration.

A small in-memory Odoo stands in for ``/json/2/`` (``OdooRPC._json2`` is
monkeypatched) and for ``/web/session/authenticate``. Its login match is
case-sensitive, like Odoo 19's ``_get_login_domain``.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_SECRET = "s3cret-Pass-42"


def _load(name: str, modname: str):
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(modname, _SCRIPTS / name)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _paths():
    return _load("local_odoo_paths.py", "local_odoo_paths_team_under_test")


class FakeOdoo:
    """Just enough of res.users / ir.model.data for team_login.py."""

    GROUPS = {
        "base.group_user": 1,
        "sales_team.group_sale_salesman": 20,
        "sales_team.group_sale_manager": 21,
        "website.group_website_designer": 30,
        "base.group_portal": 40,
    }

    def __init__(self, users, can_create=True):
        self.users = {u["id"]: dict({"active": True, "share": False, "group_ids": [1],
                                     "password": "", "email": u["login"], "name": "x"}, **u)
                      for u in users}
        self.can_create = can_create
        self.writes: list[tuple] = []

    # -- /json/2/ --------------------------------------------------------
    def json2(self, model, method, **kw):
        if model == "res.users" and method == "context_get":
            return {"uid": 2}
        if model == "res.users" and method == "has_access":
            return self.can_create
        if model == "res.users" and method == "search_read":
            return [self._fields(u, kw["fields"]) for u in self._match(kw.get("domain") or [])]
        if model == "res.users" and method == "read":
            return [self._fields(self.users[i], kw["fields"]) for i in kw["ids"]]
        if model == "res.users" and method == "create":
            vals = kw["vals_list"][0]
            new_id = max(self.users) + 1
            groups = vals.get("group_ids", [[6, 0, []]])[0][2]
            self.users[new_id] = {
                "id": new_id, "login": vals["login"], "email": vals.get("email", ""),
                "name": vals["name"], "active": True, "share": False,
                "group_ids": list(groups), "password": vals.get("password", ""),
            }
            return [new_id]
        if model == "res.users" and method == "write":
            for i in kw["ids"]:
                self.users[i].update(kw["vals"])
            self.writes.append((tuple(kw["ids"]), dict(kw["vals"])))
            return True
        if model == "ir.model.data" and method == "search_read":
            return self._xmlids(kw["domain"])
        raise AssertionError(f"unexpected {model}.{method}")

    def _match(self, domain):
        rows = list(self.users.values())
        for field, op, value in domain:
            assert field == "login" and op == "=ilike", domain
            want = value.replace("\\_", "_").replace("\\%", "%").replace("\\\\", "\\").lower()
            rows = [u for u in rows if u["login"].lower() == want]
        return rows

    @staticmethod
    def _fields(user, fields):
        return {f: user.get(f) for f in fields}

    def _xmlids(self, domain):
        d = {f: v for f, _, v in domain}
        if "res_id" in d:
            return [{"module": x.split(".")[0], "name": x.split(".")[1], "res_id": gid}
                    for x, gid in self.GROUPS.items() if gid in d["res_id"]]
        xmlid = f"{d['module']}.{d['name']}"
        return [{"res_id": self.GROUPS[xmlid]}] if xmlid in self.GROUPS else []

    # -- /web/session/authenticate ----------------------------------------
    def authenticate(self, login, password):
        for user in self.users.values():
            if user["login"] == login and user["active"]:  # case-sensitive
                if user["password"] == password:
                    return user["id"], ""
                return None, "AccessDenied"
        return None, "AccessDenied"


@pytest.fixture()
def box(tmp_path, monkeypatch):
    """A box with an ``.odoo-admin`` key under odoo-community's data dir."""
    for var in ("HH_HERMES_HOME", "HERMES_HOME", "CRM_BOT_DATA_DIR", "ODOO_WEBSITE_DATA_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    data = tmp_path / ".hermes" / "data" / "odoo-community"
    data.mkdir(parents=True)
    (data / ".odoo-admin").write_text("api_key=k\n", encoding="utf-8")
    return tmp_path


def _team(monkeypatch, odoo: FakeOdoo):
    mod = _load("team_login.py", "team_login_under_test")
    monkeypatch.setattr(mod.OdooRPC, "_json2", lambda self, m, meth, **kw: odoo.json2(m, meth, **kw))
    monkeypatch.setattr(mod, "_session_authenticate", odoo.authenticate)
    return mod


def _users():
    return [
        {"id": 2, "login": "owner@example.com"},
        {"id": 6, "login": "arjen@example.com", "group_ids": [1, 20, 30]},
    ]


# --------------------------------------------------------------------------
# normalize_login
# --------------------------------------------------------------------------


@pytest.mark.parametrize("raw, want", [
    ("Ethan@Example.test", "ethan@example.test"),
    ("  ethan@example.test \n", "ethan@example.test"),
    ("ADMIN", "admin"),
    ("admin", "admin"),
])
def test_normalize_login_strips_and_lowercases(raw, want):
    assert _paths().normalize_login(raw) == want


@pytest.mark.parametrize("raw", ["", None, "ethan", "  ", "administrator"])
def test_normalize_login_refuses_a_value_without_at(raw):
    with pytest.raises(ValueError):
        _paths().normalize_login(raw)


# --------------------------------------------------------------------------
# admin_login_and_file — four states, and the caller's own candidate list
# --------------------------------------------------------------------------


def _admin(tmp_path, bot, body):
    d = tmp_path / ".hermes" / "data" / bot
    d.mkdir(parents=True, exist_ok=True)
    (d / ".odoo-admin").write_text(body, encoding="utf-8")
    return d / ".odoo-admin"


def test_admin_state_owner_set(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    _admin(tmp_path, "crm-bot", "login=ries@example.com\npassword=p\napi_key=k\n")
    assert _paths().admin_login_and_file() == ("ries@example.com", "owner_set")


def test_admin_state_bake_placeholder(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    _admin(tmp_path, "odoo-website", "login=admin\npassword=p\napi_key=k\n")
    assert _paths().admin_login_and_file() == ("", "bake_placeholder")


def test_admin_state_key_only_for_a_hand_wired_odoo(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    _admin(tmp_path, "crm-bot", "db=website\napi_key=k\n")
    assert _paths().admin_login_and_file() == ("", "key_only")


def test_admin_state_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    assert _paths().admin_login_and_file() == ("", "missing")


def test_admin_state_caller_candidates_win(tmp_path, monkeypatch):
    """A ``*_DATA_DIR`` override is the caller's first candidate. It wins over
    the community-wide list."""
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    _admin(tmp_path, "crm-bot", "login=admin\npassword=p\napi_key=k\n")
    own = tmp_path / "override" / ".odoo-admin"
    own.parent.mkdir()
    own.write_text("login=ries@example.com\npassword=p\napi_key=k\n", encoding="utf-8")
    mod = _paths()
    assert mod.admin_login_and_file([own, *mod.admin_candidates()]) == (
        "ries@example.com", "owner_set",
    )


def test_crm_and_website_preflight_report_key_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    for var in ("CRM_BOT_DATA_DIR", "ODOO_WEBSITE_DATA_DIR"):
        monkeypatch.delenv(var, raising=False)
    _admin(tmp_path, "crm-bot", "api_key=k\n")
    root = Path(__file__).resolve().parents[3]
    for bot in ("crm-bot", "odoo-website"):
        mod = _load_from(root / bot / "scripts" / "preflight.py", f"{bot}_preflight_key_only")
        monkeypatch.setattr(mod, "_odoo_serving", lambda: False)  # hermetic
        assert mod.main() == 0
        out = capsys.readouterr().out
        assert "ADMIN_FILE: key_only" in out
        assert "JSON2: " in out


def _load_from(path: Path, modname: str):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# create
# --------------------------------------------------------------------------


def test_create_like_copies_groups_exactly_and_lowercases(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users())
    mod = _team(monkeypatch, odoo)
    monkeypatch.setenv("ETHAN_ODOO_PASSWORD", _SECRET)
    rc = mod.main([
        "create", "--login", "Ethan@Example.test", "--name", "Ethan Blake",
        "--like", "Arjen@example.com", "--password-env", "ETHAN_ODOO_PASSWORD",
    ])
    out = capsys.readouterr().out
    assert rc == 0, out
    new = next(u for u in odoo.users.values() if u["name"] == "Ethan Blake")
    assert new["login"] == "ethan@example.test"
    assert new["email"] == "ethan@example.test"
    assert sorted(new["group_ids"]) == [1, 20, 30]
    assert "CREATED ethan@example.test" in out
    assert ("GROUPS base.group_user,sales_team.group_sale_salesman,"
            "website.group_website_designer") in out
    assert "CHECK_OK ethan@example.test" in out
    assert _SECRET not in out


def test_create_groups_and_without_adjust_the_copy(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users())
    mod = _team(monkeypatch, odoo)
    rc = mod.main([
        "create", "--login", "petrus@example.com", "--name", "Petrus",
        "--like", "arjen@example.com", "--groups", "sales_team.group_sale_manager",
        "--without", "website.group_website_designer",
    ])
    out = capsys.readouterr().out
    assert rc == 0, out
    new = next(u for u in odoo.users.values() if u["name"] == "Petrus")
    assert sorted(new["group_ids"]) == [1, 20, 21]
    assert "NO_PASSWORD_YET" in out


def test_create_refuses_a_case_variant_duplicate(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users() + [{"id": 8, "login": "Ethan@example.test"}])
    mod = _team(monkeypatch, odoo)
    rc = mod.main([
        "create", "--login", "ethan@example.test", "--name", "Ethan",
        "--like", "arjen@example.com",
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "EXISTS_CASE_VARIANT Ethan@example.test" in out
    assert len(odoo.users) == 3


def test_create_refuses_an_exact_duplicate(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users())
    mod = _team(monkeypatch, odoo)
    rc = mod.main(["create", "--login", "Arjen@Example.com", "--name", "A",
                   "--groups", "base.group_user"])
    assert rc == 1
    assert "EXISTS arjen@example.com" in capsys.readouterr().out


def test_create_refuses_a_login_without_at(box, monkeypatch, capsys):
    mod = _team(monkeypatch, FakeOdoo(_users()))
    assert mod.main(["create", "--login", "ethan", "--name", "E",
                     "--groups", "base.group_user"]) == 1
    assert "LOGIN_INVALID ethan" in capsys.readouterr().out


def test_create_needs_groups(box, monkeypatch, capsys):
    mod = _team(monkeypatch, FakeOdoo(_users()))
    assert mod.main(["create", "--login", "e@x.test", "--name", "E"]) == 1
    assert "GROUPS_REQUIRED" in capsys.readouterr().out


def test_create_unknown_group_is_refused(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users())
    mod = _team(monkeypatch, odoo)
    assert mod.main(["create", "--login", "e@x.test", "--name", "E",
                     "--groups", "base.group_nope"]) == 1
    assert "GROUP_NOT_FOUND base.group_nope" in capsys.readouterr().out
    assert len(odoo.users) == 2


# --------------------------------------------------------------------------
# set-password / check / can
# --------------------------------------------------------------------------


def test_set_password_writes_and_checks(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users() + [{"id": 8, "login": "ethan@example.test"}])
    mod = _team(monkeypatch, odoo)
    monkeypatch.setenv("NEW_PW", _SECRET)
    rc = mod.main(["set-password", "--login", "Ethan@Example.test", "--password-env", "NEW_PW"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert odoo.users[8]["password"] == _SECRET
    assert "PASSWORD_SET ethan@example.test" in out
    assert "CHECK_OK ethan@example.test" in out
    assert _SECRET not in out


def test_set_password_on_a_case_variant_names_the_stored_login(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users() + [{"id": 8, "login": "Ethan@example.test"}])
    mod = _team(monkeypatch, odoo)
    monkeypatch.setenv("NEW_PW", _SECRET)
    assert mod.main(["set-password", "--login", "ethan@example.test",
                     "--password-env", "NEW_PW"]) == 1
    assert "LOGIN_CASE_MISMATCH stored=Ethan@example.test" in capsys.readouterr().out
    assert odoo.writes == []


def test_check_reports_login_case_mismatch(box, monkeypatch, capsys):
    """Turn 16 of session 3219: the stored login held a capital, the person
    typed lowercase."""
    odoo = FakeOdoo(_users() + [{"id": 8, "login": "Ethan@example.test", "password": _SECRET}])
    mod = _team(monkeypatch, odoo)
    monkeypatch.setenv("ETHAN_ODOO_PASSWORD", _SECRET)
    rc = mod.main(["check", "--login", "ethan@example.test",
                   "--password-env", "ETHAN_ODOO_PASSWORD"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "CHECK_FAILED ethan@example.test" in out
    assert "LOGIN_CASE_MISMATCH stored=Ethan@example.test" in out
    assert _SECRET not in out


def test_check_uses_the_exact_typed_string(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users() + [{"id": 8, "login": "Ethan@example.test", "password": _SECRET}])
    mod = _team(monkeypatch, odoo)
    monkeypatch.setenv("PW", _SECRET)
    assert mod.main(["check", "--login", "Ethan@example.test", "--password-env", "PW"]) == 0
    assert "CHECK_OK Ethan@example.test" in capsys.readouterr().out


def test_check_names_a_rejected_password_and_an_unknown_login(box, monkeypatch, capsys):
    odoo = FakeOdoo(_users() + [{"id": 8, "login": "ethan@example.test", "password": "other"}])
    mod = _team(monkeypatch, odoo)
    monkeypatch.setenv("PW", _SECRET)
    assert mod.main(["check", "--login", "ethan@example.test", "--password-env", "PW"]) == 1
    assert "PASSWORD_REJECTED ethan@example.test" in capsys.readouterr().out
    assert mod.main(["check", "--login", "nobody@example.test", "--password-env", "PW"]) == 1
    assert "LOGIN_NOT_FOUND nobody@example.test" in capsys.readouterr().out


def test_check_never_calls_a_public_url(box, monkeypatch):
    mod = _load("team_login.py", "team_login_url_under_test")
    seen = []

    class _Opener:
        def open(self, req, timeout=0):
            seen.append(req.full_url)
            raise OSError("refused")

    monkeypatch.setattr(mod.urllib.request, "build_opener", lambda *a: _Opener())
    assert mod._session_authenticate("e@x.test", "pw") == (None, "odoo_down")
    assert seen == ["http://127.0.0.1:8069/web/session/authenticate"]


def test_can_reports_yes_and_no(box, monkeypatch, capsys):
    mod = _team(monkeypatch, FakeOdoo(_users(), can_create=True))
    assert mod.main(["can"]) == 0
    out = capsys.readouterr().out
    assert "KEY_USER owner@example.com" in out
    assert "CAN_CREATE_USERS yes" in out
    mod = _team(monkeypatch, FakeOdoo(_users(), can_create=False))
    assert mod.main(["can"]) == 0
    assert "CAN_CREATE_USERS no" in capsys.readouterr().out


def test_no_password_on_argv(capsys):
    """The parser has no option that takes a password value. ``--password``
    is not an abbreviation of ``--password-env``, and a refused argument is
    never echoed back."""
    mod = _load("team_login.py", "team_login_argv_under_test")
    for argv in (
        ["create", "--login", "e@x.test", "--name", "E", "--password", _SECRET],
        ["set-password", "--login", "e@x.test", "--password", _SECRET],
        ["check", "--login", "e@x.test", "--password", _SECRET],
        ["check", "--login", "e@x.test", "--password-env", "PW", _SECRET],
    ):
        with pytest.raises(SystemExit):
            mod.main(argv)
        captured = capsys.readouterr()
        assert _SECRET not in captured.out + captured.err
    source = (_SCRIPTS / "team_login.py").read_text(encoding="utf-8")
    assert '"--password"' not in source


def test_a_password_in_the_env_name_slot_is_not_echoed(box, monkeypatch, capsys):
    mod = _team(monkeypatch, FakeOdoo(_users()))
    assert mod.main(["check", "--login", "e@x.test", "--password-env", _SECRET]) == 1
    out = capsys.readouterr().out
    assert "BAD_ENV_NAME" in out
    assert _SECRET not in out


def test_empty_password_env_is_refused(box, monkeypatch, capsys):
    mod = _team(monkeypatch, FakeOdoo(_users()))
    monkeypatch.delenv("MISSING_PW", raising=False)
    assert mod.main(["check", "--login", "e@x.test", "--password-env", "MISSING_PW"]) == 1
    assert "EMPTY_ENV MISSING_PW" in capsys.readouterr().out


# --------------------------------------------------------------------------
# lowercase-all — the lowercase-logins migration
# --------------------------------------------------------------------------


def _migration_users():
    return [
        {"id": 2, "login": "Owner@Example.com"},
        {"id": 8, "login": "Ethan@example.test"},
        {"id": 9, "login": "ARJEN@example.com", "email": "arjen.private@example.com"},
        {"id": 10, "login": "arjen@example.com"},
        {"id": 11, "login": "Client@example.com", "share": True},
    ]


def test_lowercase_all_renames_leaves_twins_and_is_idempotent(box, monkeypatch, capsys):
    admin = box / ".hermes" / "data" / "odoo-website" / ".odoo-admin"
    admin.parent.mkdir(parents=True)
    admin.write_text(f"login=Owner@Example.com\npassword={_SECRET}\napi_key=k\n",
                     encoding="utf-8")
    os.chmod(admin, 0o600)
    odoo = FakeOdoo(_migration_users())
    mod = _team(monkeypatch, odoo)

    assert mod.main(["lowercase-all"]) == 0
    out = capsys.readouterr().out
    assert "LOWERCASED Owner@Example.com -> owner@example.com" in out
    assert "LOWERCASED Ethan@example.test -> ethan@example.test" in out
    assert "TWIN ARJEN@example.com arjen@example.com" in out
    assert "LOWERCASE_DONE changed=2 twins=1" in out
    assert odoo.users[8]["email"] == "ethan@example.test"
    assert odoo.users[9]["login"] == "ARJEN@example.com"      # twin left alone
    assert odoo.users[10]["login"] == "arjen@example.com"
    assert odoo.users[11]["login"] == "Client@example.com"    # portal untouched
    assert f"ADMIN_FILE_UPDATED {admin}" in out
    text = admin.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "login=owner@example.com"
    assert f"password={_SECRET}" in text
    assert oct(admin.stat().st_mode & 0o777) == "0o600"
    assert _SECRET not in out

    writes = len(odoo.writes)
    assert mod.main(["lowercase-all"]) == 0
    out = capsys.readouterr().out
    assert "LOWERCASE_DONE changed=0 twins=1" in out
    assert "LOWERCASED" not in out
    assert "ADMIN_FILE_UPDATED" not in out
    assert len(odoo.writes) == writes


def test_lowercase_all_keeps_a_different_email(box, monkeypatch, capsys):
    odoo = FakeOdoo([{"id": 2, "login": "Sam@example.com", "email": "sam@home.test"}])
    mod = _team(monkeypatch, odoo)
    assert mod.main(["lowercase-all"]) == 0
    assert odoo.users[2]["login"] == "sam@example.com"
    assert odoo.users[2]["email"] == "sam@home.test"


def test_lowercase_all_without_a_key_has_nothing_to_do(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    mod = _load("team_login.py", "team_login_nokey_under_test")
    assert mod.main(["lowercase-all"]) == 0
    assert "LOWERCASE_NOTHING_TO_DO no_key" in capsys.readouterr().out


def test_lowercase_all_waits_when_odoo_is_installed_but_down(box, monkeypatch, capsys):
    (box / "odoo-site" / "odoo").mkdir(parents=True)
    mod = _load("team_login.py", "team_login_down_under_test")

    def down(self, model, method, **kw):
        raise RuntimeError("ODOO_RPC_FAILED odoo_down: refused")

    monkeypatch.setattr(mod.OdooRPC, "_json2", down)
    assert mod.main(["lowercase-all"]) == 0
    assert "LOWERCASE_LATER odoo_down" in capsys.readouterr().out


def test_lowercase_all_without_odoo_has_nothing_to_do(box, monkeypatch, capsys):
    mod = _load("team_login.py", "team_login_noodoo_under_test")

    def down(self, model, method, **kw):
        raise RuntimeError("ODOO_RPC_FAILED odoo_down: refused")

    monkeypatch.setattr(mod.OdooRPC, "_json2", down)
    assert mod.main(["lowercase-all"]) == 0
    assert "LOWERCASE_NOTHING_TO_DO no_odoo" in capsys.readouterr().out


# --------------------------------------------------------------------------
# the migration manifest reaches the bot
# --------------------------------------------------------------------------


def test_migrations_line_is_pending_then_none(box, monkeypatch):
    mod = _paths()
    line = mod.migrations_line()
    assert line.startswith("ODOO_COMMUNITY_MIGRATIONS: pending — lowercase-logins (checklist)")
    assert "odoo-community references/migrations.md" in line
    migrate = _load("migrate.py", "community_migrate_under_test")
    migrate.main(["--mark", "lowercase-logins"])
    marker = box / ".hermes" / "data" / "odoo-community" / "migrations.json"
    assert json.loads(marker.read_text())["applied"] == ["lowercase-logins"]
    assert mod.migrations_line() == "ODOO_COMMUNITY_MIGRATIONS: none"


def test_migration_ref_section_exists():
    bundle = Path(__file__).resolve().parents[2]
    manifest = (bundle / "migrations.yaml").read_text(encoding="utf-8")
    assert "id: lowercase-logins" in manifest
    doc = (bundle / "references" / "migrations.md").read_text(encoding="utf-8")
    assert "## lowercase-logins" in doc
    assert "team_login.py lowercase-all" in doc
    assert "migrate.py --mark lowercase-logins" in doc
