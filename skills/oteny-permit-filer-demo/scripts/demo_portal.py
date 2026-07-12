"""The demo permit portal — a tiny local government-portal stand-in.

A three-page wizard (details -> site -> review) that mints a confirmation number
on submit, plus a machine-readable audit endpoint so tests can assert ground
truth. Pure stdlib, no framework; the page shapes deliberately exercise what a
real portal throws at a filing bot:

* stable ``id == name`` text inputs and native ``<select>``s (CSS-selectable),
* radio groups that carry a *name* only (target ``input[name=x][value=Yes]``),
* an unlock-then-set interaction: the "local municipalities only" checkbox on
  page 2 hides/disables the non-local options until unchecked — set it FIRST,
  then select, in the same ``browser_fill_form`` call,
* a declaration checkbox gating the final submit (the irreversible step your
  skill must NEVER batch — fresh snapshot, explicit click),
* a confirmation page that is the ONLY source of the permit number.

Run:  python3 scripts/demo_portal.py --port 8099
Then: expose it to your dev bot (any HTTPS tunnel) and bind it as the bot's
portal double (see the bundle README), or drive it from a local browser to
derive/verify the selector map in permit-filing/references/form-selectors.md.

Endpoints: /healthz (JSON ok) · /_audit (JSON: submitted applications).
"""

from __future__ import annotations

import argparse
import json
import secrets
import threading
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

MUNICIPALITIES_LOCAL = ["Rivertown", "Lakeside", "Bridgeport"]
MUNICIPALITIES_OTHER = ["Farfield", "Overhill", "Distantvale"]
PERMIT_TYPES = ["Street works", "Scaffolding", "Event", "Excavation"]


class _Store:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.drafts: dict[str, dict] = {}
        self.submitted: list[dict] = []

    def new_draft(self) -> str:
        did = secrets.token_hex(6)
        with self.lock:
            self.drafts[did] = {}
        return did

    def submit(self, did: str) -> dict:
        with self.lock:
            fields = self.drafts.pop(did, {})
            number = f"P-{secrets.randbelow(900000) + 100000}"
            rec = {"id": did, "number": number, "fields": fields}
            self.submitted.append(rec)
            return rec


STORE = _Store()


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html><head><title>{escape(title)} — Demo Permit "
            f"Portal</title></head><body><h1>{escape(title)}</h1>{body}</body></html>")


def _text(name: str, label: str, value: str = "") -> str:
    return (f'<p><label for="{name}">{escape(label)}</label><br>'
            f'<input type="text" id="{name}" name="{name}" value="{escape(value)}"></p>')


def _radio(name: str, label: str, options: list[str]) -> str:
    opts = " ".join(
        f'<label><input type="radio" name="{name}" value="{escape(o)}"> {escape(o)}</label>'
        for o in options
    )
    return f"<p><strong>{escape(label)}</strong><br>{opts}</p>"


def _details_html(did: str, d: dict) -> str:
    types = "".join(
        f'<option value="{escape(t)}">{escape(t)}</option>' for t in PERMIT_TYPES
    )
    return _page("Application details", f"""
  <form method="POST" action="/application/{did}/details">
  {_text("applicant_name", "Applicant name", d.get("applicant_name", ""))}
  {_text("company", "Company", d.get("company", ""))}
  <p><label for="permit_type">Permit type</label><br>
  <select id="permit_type" name="permit_type"><option value="">Choose…</option>{types}</select></p>
  {_text("start_date", "Start date (dd-mm-yyyy)", d.get("start_date", ""))}
  <p><button type="submit">Next</button></p>
  </form>""")


def _site_html(did: str, d: dict) -> str:
    opts = "".join(
        f'<option value="{escape(m)}" data-local="1">{escape(m)}</option>'
        for m in MUNICIPALITIES_LOCAL
    ) + "".join(
        f'<option value="{escape(m)}" data-local="0">{escape(m)}</option>'
        for m in MUNICIPALITIES_OTHER
    )
    return _page("Work site", f"""
  <form method="POST" action="/application/{did}/site">
  <p><label><input type="checkbox" id="local_only" name="local_only" checked>
  Show local municipalities only</label></p>
  <p><label for="municipality">Municipality</label><br>
  <select id="municipality" name="municipality"><option value="">Choose…</option>{opts}</select></p>
  {_text("street", "Street", d.get("street", ""))}
  {_text("house_number", "House number", d.get("house_number", ""))}
  {_text("postcode", "Postcode", d.get("postcode", ""))}
  {_text("city", "City", d.get("city", ""))}
  {_radio("has_insurance", "Does the applicant hold liability insurance?", ["Yes", "No"])}
  {_radio("night_work", "Will work happen at night?", ["Yes", "No"])}
  <p><button type="submit">Next</button></p>
  </form>
  <script>
  (function () {{
    var box = document.getElementById('local_only');
    var sel = document.getElementById('municipality');
    function sync() {{
      for (var i = 0; i < sel.options.length; i++) {{
        var o = sel.options[i];
        if (o.dataset.local === '0') {{ o.hidden = box.checked; o.disabled = box.checked; }}
      }}
    }}
    box.addEventListener('change', sync); sync();
  }})();
  </script>""")


def _review_html(did: str, d: dict) -> str:
    rows = "".join(
        f"<tr><td>{escape(k)}</td><td>{escape(str(v))}</td></tr>"
        for k, v in sorted(d.items())
    )
    return _page("Review and submit", f"""
  <table border="1">{rows}</table>
  <form method="POST" action="/application/{did}/submit">
  <p><label><input type="checkbox" name="declaration"> I declare the information
  above is correct.</label></p>
  <p><button type="submit">Submit application</button></p>
  </form>""")


def _confirmation_html(rec: dict) -> str:
    return _page("Application received", f"""
  <p>Your application has been received.</p>
  <p><strong>Confirmation number: {escape(rec["number"])}</strong></p>
  <p>Keep this number for your records.</p>""")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html: str, code: int = 200):
        self._send(code, html.encode("utf-8"))

    def _redirect(self, path: str):
        self.send_response(303)
        self.send_header("Location", path)
        self.end_headers()

    def log_message(self, fmt, *args):  # quieter default log line
        print(f"[portal] {fmt % args}")

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._send(200, b'{"ok": true}', "application/json")
        elif path == "/_audit":
            body = json.dumps({"submitted": STORE.submitted}).encode()
            self._send(200, body, "application/json")
        elif path in ("/", "/portal"):
            self._html(_page("Demo Permit Portal",
                             '<p><a href="/portal/new">+ New application</a></p>'))
        elif path == "/portal/new":
            did = STORE.new_draft()
            self._redirect(f"/application/{did}/details")
        else:
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "application":
                did, step = parts[1], parts[2]
                d = STORE.drafts.get(did)
                if d is None:
                    self._html(_page("Not found", "<p>Unknown application.</p>"), 404)
                elif step == "details":
                    self._html(_details_html(did, d))
                elif step == "site":
                    self._html(_site_html(did, d))
                elif step == "review":
                    self._html(_review_html(did, d))
                else:
                    self._html(_page("Not found", "<p>No such step.</p>"), 404)
            else:
                self._html(_page("Not found", "<p>No such page.</p>"), 404)

    def do_POST(self):
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        posted = {k: v[0] for k, v in parse_qs(
            self.rfile.read(length).decode(), keep_blank_values=True).items()}
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "application":
            did, step = parts[1], parts[2]
            d = STORE.drafts.get(did)
            if d is None:
                self._html(_page("Not found", "<p>Unknown application.</p>"), 404)
                return
            if step == "details":
                d.update(posted)
                self._redirect(f"/application/{did}/site")
            elif step == "site":
                d.update(posted)
                self._redirect(f"/application/{did}/review")
            elif step == "submit":
                if posted.get("declaration") not in ("on", "true", "1"):
                    self._html(_review_html(did, d))
                    return
                rec = STORE.submit(did)
                # POST-redirect-GET so the confirmation URL is shareable/reloadable.
                self._redirect(f"/confirmation/{rec['id']}")
            else:
                self._html(_page("Not found", "<p>No such step.</p>"), 404)
        else:
            self._html(_page("Not found", "<p>No such page.</p>"), 404)


class _ConfirmationMixin:
    pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the demo permit portal.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8099)
    args = ap.parse_args()

    # Serve confirmations from the submitted list (drafts are consumed on submit).
    orig_get = Handler.do_GET

    def do_get(self):
        path = urlsplit(self.path).path
        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "confirmation":
            rec = next((r for r in STORE.submitted if r["id"] == parts[1]), None)
            if rec is None:
                self._html(_page("Not found", "<p>Unknown confirmation.</p>"), 404)
            else:
                self._html(_confirmation_html(rec))
            return
        orig_get(self)

    Handler.do_GET = do_get
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"demo permit portal listening on http://{args.host}:{args.port}/portal")
    srv.serve_forever()


if __name__ == "__main__":
    main()
