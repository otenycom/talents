"""CrmBot must never invent a PeekMSX host or a lead id when Odoo is down."""
import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def test_public_url_is_opt_in_and_never_peekmsx():
    sys.path.insert(0, str(_SCRIPTS))
    import upsert_lead
    os.environ.pop("CRM_PUBLIC_URL", None)
    assert upsert_lead._public_lead_url(99) is None
    os.environ["CRM_PUBLIC_URL"] = "https://example.oteny.bot"
    assert upsert_lead._public_lead_url(99) == "https://example.oteny.bot/odoo/crm/99"
    text = (_SCRIPTS / "upsert_lead.py").read_text(encoding="utf-8")
    assert "lead-bot.oteny.bot" not in text


def test_down_odoo_prints_null_lead_id(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_HOME", str(tmp_path))
    (tmp_path / ".hermes" / "data" / "crm-bot").mkdir(parents=True)
    r = subprocess.run(
        [sys.executable, str(_SCRIPTS / "upsert_lead.py")],
        input=json.dumps({"name": "Jane", "event": "OXP"}),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert r.returncode != 0
    payload = json.loads(r.stdout.strip().splitlines()[-1])
    assert payload["lead_id"] is None
    assert payload["url"] is None
    assert "error" in payload


def test_find_partner_signature_includes_phone():
    sys.path.insert(0, str(_SCRIPTS))
    import inspect
    import odoo_rpc
    params = inspect.signature(odoo_rpc.OdooRPC.find_partner).parameters
    assert "phone" in params
