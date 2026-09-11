#!/usr/bin/env python3
"""write_profile.py — persist WebsiteBot first-run answers where the box can write.

Do not use Hermes ``write_file`` for this path. That tool mkdir's as the
sandbox user and fails when ``~/.hermes/data`` is not writable. This
script writes ``profile.yaml`` under ``~/.hermes/data/odoo-website``
when that folder is writable. When it is not, it writes
``~/.hermes/odoo-website/profile.yaml``. It exits non-zero if the file
did not land.

    python3 …/scripts/write_profile.py --site-name "Bella Cafe" \\
        --site-purpose "menu + hours" --site-slug bella \\
        --owner-email owner@example.com --language nl

Exit 0 + ``PROFILE_WRITTEN <path>`` on success.
Exit 1 + ``PROFILE_WRITE_FAILED …`` on failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from website_paths import writable_data_dir

_FIELDS = (
    "site_name",
    "site_purpose",
    "site_slug",
    "owner_email",
    "language",
    "timezone",
    "name",
    "odoo_locus",
    "build_backend",
    "git_customer_facing",
    "git_remote_url",
)


def write_profile(**raw: str) -> Path:
    """Write ``profile.yaml``. Raise OSError when the directory or file cannot land."""
    email = (raw.get("owner_email") or "").strip()
    if not email or "@" not in email:
        raise ValueError("owner_email")
    slug = (raw.get("site_slug") or "").strip()
    values = {
        "site_name": (raw.get("site_name") or "").strip(),
        "site_purpose": (raw.get("site_purpose") or "").strip(),
        "site_slug": slug,
        "owner_email": email,
        "language": (raw.get("language") or "en").strip() or "en",
        "timezone": (raw.get("timezone") or "").strip(),
        "name": (raw.get("name") or "").strip(),
        "odoo_locus": (raw.get("odoo_locus") or "local").strip() or "local",
        "build_backend": (raw.get("build_backend") or "module").strip() or "module",
        "git_customer_facing": (raw.get("git_customer_facing") or "false").strip() or "false",
        "git_remote_url": (raw.get("git_remote_url") or "").strip(),
    }
    dest = writable_data_dir()
    path = dest / "profile.yaml"
    path.write_text("".join(f"{key}: {values[key]}\n" for key in _FIELDS), encoding="utf-8")
    if not path.is_file() or not path.stat().st_size:
        raise OSError("profile_missing_after_write")
    return path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-name", default="")
    p.add_argument("--site-purpose", default="")
    p.add_argument("--site-slug", default="")
    p.add_argument("--owner-email", required=True)
    p.add_argument("--language", default="en")
    p.add_argument("--timezone", default="")
    p.add_argument("--name", default="")
    p.add_argument("--odoo-locus", default="local")
    p.add_argument("--build-backend", default="module")
    p.add_argument("--git-customer-facing", default="false")
    p.add_argument("--git-remote-url", default="")
    args = p.parse_args()
    try:
        path = write_profile(
            site_name=args.site_name,
            site_purpose=args.site_purpose,
            site_slug=args.site_slug,
            owner_email=args.owner_email,
            language=args.language,
            timezone=args.timezone,
            name=args.name,
            odoo_locus=args.odoo_locus,
            build_backend=args.build_backend,
            git_customer_facing=args.git_customer_facing,
            git_remote_url=args.git_remote_url,
        )
    except ValueError as exc:
        print(f"PROFILE_WRITE_FAILED bad_{exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        err = str(exc)
        if getattr(exc, "errno", None) == 13 or "Permission denied" in err:
            print("PROFILE_WRITE_FAILED permission_denied", file=sys.stderr)
        else:
            print(f"PROFILE_WRITE_FAILED {exc!r}", file=sys.stderr)
        return 1
    print(f"PROFILE_WRITTEN {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
