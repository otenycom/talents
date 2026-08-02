#!/usr/bin/env python3
"""site_module.py — locked MODULE build path for WebsiteBot.

Local Max/VM only. Scaffold an addon under ~/odoo-site/addons/oteny_site_<slug>/,
edit homepage (QWeb + optional SCSS/Python), git-commit, then -u via upgrade.

    python3 …/site_module.py init --slug moondive --name "Moon Skydive Club"
    python3 …/site_module.py set-homepage --title "…" --body-html "…"
    python3 …/site_module.py upgrade
    python3 …/site_module.py git-remote --url git@github.com:org/repo.git   # after intake

Do NOT use this against Odoo Online. Non-Max owners must upgrade first:
``/oteny_subscribe upgrade max``.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
from pathlib import Path

_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,28}[a-z0-9])?$")


def _home() -> Path:
    return Path(os.environ.get("HH_HOME") or os.path.expanduser("~"))


def _base() -> Path:
    return _home() / "odoo-site"


def _addons() -> Path:
    return _base() / "addons"


def _data_dir() -> Path:
    override = os.environ.get("ODOO_WEBSITE_DATA_DIR")
    if override:
        return Path(override)
    return _home() / ".hermes" / "data" / "odoo-website"


def _load_profile() -> dict:
    path = _data_dir() / "profile.yaml"
    if not path.exists():
        return {}
    out: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def module_name(slug: str) -> str:
    safe = slug.strip().lower().replace("-", "_")
    if not re.match(r"^[a-z][a-z0-9_]{1,40}$", safe):
        raise SystemExit(f"SITE_MODULE_ERR bad slug for module name: {slug!r}")
    return f"oteny_site_{safe}"


def module_dir(slug: str) -> Path:
    return _addons() / module_name(slug)


def _resolve_slug(cli_slug: str | None) -> str:
    slug = (cli_slug or _load_profile().get("site_slug") or "").strip().lower()
    if not slug or not _SLUG_RE.match(slug):
        raise SystemExit(
            "SITE_MODULE_ERR need --slug or profile.yaml site_slug "
            "(3–30 chars, lowercase/digits/hyphens)"
        )
    return slug


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=check,
        capture_output=True, text=True,
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _homepage_xml(mod: str, title: str, body_html: str) -> str:
    # Escape for embedding inside an XML arch attribute-less element body.
    # body_html is trusted owner content the bot already sanitized for publish.
    t = html.escape(title)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <record id="homepage_view" model="ir.ui.view">
    <field name="name">{t}</field>
    <field name="type">qweb</field>
    <field name="key">{mod}.homepage</field>
    <field name="arch" type="xml">
      <t t-name="{mod}.homepage">
        <t t-call="website.layout">
          <div id="wrap" class="oe_structure oteny_site_wrap">
            <section class="s_text_block pt48 pb48">
              <div class="container">
                <h1 class="oteny_site_title">{t}</h1>
                <div class="oteny_site_body">{body_html}</div>
              </div>
            </section>
          </div>
        </t>
      </t>
    </field>
  </record>
  <record id="homepage_page" model="website.page">
    <field name="name">{t}</field>
    <field name="url">/</field>
    <field name="view_id" ref="homepage_view"/>
    <field name="is_published" eval="True"/>
    <field name="website_indexed" eval="True"/>
  </record>
</odoo>
'''


def _manifest(mod: str, name: str) -> str:
    return f'''# -*- coding: utf-8 -*-
{{
    "name": {name!r},
    "version": "1.0.0",
    "category": "Website",
    "summary": "Oteny WebsiteBot site module (bot-owned git)",
    "depends": ["website"],
    "data": [
        "data/website_homepage.xml",
    ],
    "assets": {{
        "web.assets_frontend": [
            "{mod}/static/src/scss/site.scss",
        ],
    }},
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}}
'''


def _hooks_py(mod: str) -> str:
    return f'''# -*- coding: utf-8 -*-
"""Post-init: make this module's page the website homepage."""


def post_init_hook(env):
    page = env.ref("{mod}.homepage_page", raise_if_not_found=False)
    website = env.ref("website.default_website", raise_if_not_found=False)
    if page and website:
        website.sudo().write({{"homepage_id": page.id}})
'''


def _scss() -> str:
    return """/* Oteny site module — bot-editable frontend styles */
.oteny_site_wrap .oteny_site_title {
  letter-spacing: 0.02em;
}
.oteny_site_wrap .oteny_site_body {
  font-size: 1.125rem;
  line-height: 1.6;
}
"""


def _gitignore() -> str:
    return "__pycache__/\n*.pyc\n.DS_Store\n"


def cmd_init(args: argparse.Namespace) -> int:
    slug = _resolve_slug(args.slug)
    name = (args.name or _load_profile().get("site_name") or slug).strip()
    mod = module_name(slug)
    root = module_dir(slug)
    _addons().mkdir(parents=True, exist_ok=True)
    if (root / "__manifest__.py").exists() and not args.force:
        print(f"SITE_MODULE_OK already {root}")
        return 0
    title = name
    body = f"<p>{html.escape(name)}</p>"
    _write(root / "__init__.py", "from . import hooks\n")
    _write(root / "hooks.py", _hooks_py(mod))
    _write(root / "__manifest__.py", _manifest(mod, name))
    _write(root / "data" / "website_homepage.xml", _homepage_xml(mod, title, body))
    _write(root / "static" / "src" / "scss" / "site.scss", _scss())
    _write(root / "controllers" / "__init__.py", "# Optional HTTP controllers — bot may add.\n")
    _write(root / "models" / "__init__.py", "# Optional models — bot may add.\n")
    _write(root / ".gitignore", _gitignore())
    _write(root / "README.md", f"# {name}\n\nBot-owned WebsiteBot site module (`{mod}`).\n")
    if not (root / ".git").exists():
        _git(root, "init")
        _git(root, "config", "user.email", "websitebot@oteny.local")
        _git(root, "config", "user.name", "WebsiteBot")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", f"chore: scaffold {mod}")
    # Persist backend choice on profile if missing.
    prof = _data_dir() / "profile.yaml"
    if prof.exists():
        text = prof.read_text(encoding="utf-8")
        if "build_backend:" not in text:
            with prof.open("a", encoding="utf-8") as fh:
                fh.write("\nodoo_locus: local\nbuild_backend: module\n")
        if "git_customer_facing:" not in text:
            with prof.open("a", encoding="utf-8") as fh:
                fh.write("git_customer_facing: false\ngit_remote_url: \"\"\n")
    print(f"SITE_MODULE_OK init {mod} path={root}")
    return 0


def cmd_set_homepage(args: argparse.Namespace) -> int:
    slug = _resolve_slug(args.slug)
    mod = module_name(slug)
    root = module_dir(slug)
    if not (root / "__manifest__.py").exists():
        raise SystemExit(f"SITE_MODULE_ERR run init first ({root} missing)")
    title = (args.title or "").strip()
    body = (args.body_html or "").strip()
    if not title or not body:
        raise SystemExit("SITE_MODULE_ERR --title and --body-html required")
    xml_path = root / "data" / "website_homepage.xml"
    _write(xml_path, _homepage_xml(mod, title, body))
    if (root / ".git").exists():
        _git(root, "add", "data/website_homepage.xml")
        # commit may be empty if unchanged
        _git(root, "commit", "-m", f"content: homepage — {title}", check=False)
    # Install or upgrade
    rc = _upgrade(slug)
    if rc != 0:
        return rc
    print(f"SITE_MODULE_OK homepage title={title!r}")
    return 0


def _odoo_bin_env() -> dict:
    base = _base()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(base / "odoo")
    return env


def _stop_odoo() -> None:
    # Best-effort: free port 8069 so -u can run --stop-after-init cleanly.
    subprocess.run(
        ["pkill", "-f", r"python -m odoo -d website"],
        check=False, capture_output=True,
    )


def _upgrade(slug: str) -> int:
    mod = module_name(slug)
    base = _base()
    venv_py = base / "venv" / "bin" / "python"
    addons = f"{base / 'odoo' / 'addons'},{base / 'addons'}"
    if not venv_py.exists():
        raise SystemExit("SITE_MODULE_ERR ~/odoo-site not installed")
    _stop_odoo()
    # Detect install vs upgrade
    marker = base / "addons" / f".installed-{mod}"
    action = "-u" if marker.exists() else "-i"
    cmd = [
        str(venv_py), "-m", "odoo",
        "-d", "website", action, mod,
        "--stop-after-init", "--without-demo=True",
        f"--db_host={base / 'pgdata'}", "--db_port=5432", "--db_user=odoo",
        f"--addons-path={addons}",
        f"--data-dir={base / 'odoo-data'}",
        "--http-port=8069", "--http-interface=127.0.0.1", "--workers=0",
    ]
    log = base / "odoo.log"
    with log.open("a", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, env=_odoo_bin_env(), stdout=fh, stderr=fh)
    if proc.returncode != 0:
        print(f"SITE_MODULE_ERR odoo {action} {mod} failed rc={proc.returncode}",
              file=sys.stderr)
        return proc.returncode
    marker.write_text("ok\n", encoding="utf-8")
    # Bring the site back up
    ensure = Path(__file__).resolve().parent / "ensure_site.sh"
    subprocess.run(["sh", str(ensure)], check=False)
    print(f"SITE_MODULE_OK upgrade {action} {mod}")
    return 0


def cmd_upgrade(args: argparse.Namespace) -> int:
    slug = _resolve_slug(args.slug)
    if not (module_dir(slug) / "__manifest__.py").exists():
        raise SystemExit("SITE_MODULE_ERR run init first")
    return _upgrade(slug)


def cmd_git_remote(args: argparse.Namespace) -> int:
    """Record remote URL after credential intake; push if credentials work."""
    slug = _resolve_slug(args.slug)
    root = module_dir(slug)
    url = (args.url or "").strip()
    if not url:
        raise SystemExit("SITE_MODULE_ERR --url required")
    if not (root / ".git").exists():
        raise SystemExit("SITE_MODULE_ERR no git repo — run init")
    # idempotent remote
    _git(root, "remote", "remove", "origin", check=False)
    _git(root, "remote", "add", "origin", url)
    push = _git(root, "push", "-u", "origin", "HEAD", check=False)
    prof = _data_dir() / "profile.yaml"
    if prof.exists():
        text = prof.read_text(encoding="utf-8")
        lines = []
        for line in text.splitlines():
            if line.startswith("git_customer_facing:") or line.startswith("git_remote_url:"):
                continue
            lines.append(line)
        lines.append("git_customer_facing: true")
        lines.append(f"git_remote_url: {url!r}")
        prof.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if push.returncode != 0:
        print(f"SITE_MODULE_OK remote set; push pending ({push.stderr.strip()[:200]})")
        return 0
    print("SITE_MODULE_OK remote + push")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--slug", default="")
    p_init.add_argument("--name", default="")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_home = sub.add_parser("set-homepage")
    p_home.add_argument("--slug", default="")
    p_home.add_argument("--title", required=True)
    p_home.add_argument("--body-html", required=True)
    p_home.set_defaults(func=cmd_set_homepage)

    p_up = sub.add_parser("upgrade")
    p_up.add_argument("--slug", default="")
    p_up.set_defaults(func=cmd_upgrade)

    p_rem = sub.add_parser("git-remote")
    p_rem.add_argument("--slug", default="")
    p_rem.add_argument("--url", required=True)
    p_rem.set_defaults(func=cmd_git_remote)

    args = p.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
