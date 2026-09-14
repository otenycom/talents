"""pin_crm_home.py writes CRM first; install_modules.sh calls it for crm."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_BUNDLE = Path(__file__).resolve().parents[2]
_SCRIPT = _BUNDLE / "scripts" / "pin_crm_home.py"
_INSTALL = _BUNDLE / "scripts" / "install_modules.sh"


def _load():
    spec = importlib.util.spec_from_file_location("pin_crm_home", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Rec:
    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


def test_apply_pin_skips_when_crm_is_missing():
    mod = _load()
    commits = []

    def ref(xmlid, raise_if_not_found=True):
        return None

    assert mod.apply_pin(ref, lambda: commits.append(1)) == "CRM_HOME_SKIPPED no_crm"
    assert commits == []


def test_apply_pin_writes_sequence_and_home_action():
    mod = _load()
    crm = _Rec(sequence=25)
    action = _Rec(id=91)
    admin = _Rec(action_id=_Rec(id=False))
    table = {
        mod.CRM_MENU: crm,
        mod.CRM_ACTION: action,
        mod.ADMIN_USER: admin,
    }
    commits = []

    def ref(xmlid, raise_if_not_found=True):
        return table.get(xmlid)

    line = mod.apply_pin(ref, lambda: commits.append(1))
    assert line == "CRM_HOME_PINNED sequence,home_action"
    assert crm.sequence == 1
    assert admin.action_id is action
    assert commits == [1]


def test_apply_pin_is_idempotent():
    mod = _load()
    action = _Rec(id=91)
    crm = _Rec(sequence=1)
    admin = _Rec(action_id=action)
    table = {
        mod.CRM_MENU: crm,
        mod.CRM_ACTION: action,
        mod.ADMIN_USER: admin,
    }
    commits = []

    def ref(xmlid, raise_if_not_found=True):
        return table.get(xmlid)

    assert mod.apply_pin(ref, lambda: commits.append(1)) == "CRM_HOME_PINNED already"
    assert crm.sequence == 1
    assert commits == [1]


def test_install_modules_pins_crm_only():
    text = _INSTALL.read_text(encoding="utf-8")
    assert "pin_crm_home.py" in text
    assert "--require-crm" in text
    crm_case = text.index("*,crm,*)")
    pin_call = text.index("pin_crm_home.py")
    assert crm_case < pin_call
    assert "website,*)" not in text.split("pin_crm_home.py", 1)[0][-80:]


def test_skill_says_install_modules_pins_crm():
    import re

    skill = re.sub(r"\s+", " ", (_BUNDLE / "SKILL.md").read_text(encoding="utf-8"))
    assert "puts CRM first in the app menu" in skill
    assert "not Discuss" in skill
    assert "pin_crm_home.py" in (
        _BUNDLE / "required_artifacts.yaml"
    ).read_text(encoding="utf-8")
