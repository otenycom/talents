#!/usr/bin/env python3
"""write_profile.py — persist CrmBot first-run answers where the box can write.

Do not use Hermes ``write_file`` for this path. That tool mkdir's as the
sandbox user and fails when ``~/.hermes/data`` is not writable. This
script writes ``profile.yaml`` under ``~/.hermes/data/crm-bot`` when
that folder is writable. When it is not, it writes
``~/.hermes/crm-bot/profile.yaml``. It exits non-zero if the file did
not land.

    python3 …/scripts/write_profile.py --event-name OXP \\
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
from crm_paths import writable_data_dir

_FIELDS = (
    "event_name",
    "owner_email",
    "language",
    "timezone",
    "name",
    "odoo_locus",
)


def write_profile(
    *,
    event_name: str,
    owner_email: str,
    language: str = "en",
    timezone: str = "",
    name: str = "",
    odoo_locus: str = "local",
) -> Path:
    """Write ``profile.yaml``. Raise OSError when the directory or file cannot land."""
    email = (owner_email or "").strip()
    if not email or "@" not in email:
        raise ValueError("owner_email")
    values = {
        "event_name": (event_name or "").strip(),
        "owner_email": email,
        "language": (language or "en").strip() or "en",
        "timezone": (timezone or "").strip(),
        "name": (name or "").strip(),
        "odoo_locus": (odoo_locus or "local").strip() or "local",
    }
    dest = writable_data_dir()
    path = dest / "profile.yaml"
    body = "".join(f"{key}: {values[key]}\n" for key in _FIELDS)
    path.write_text(body, encoding="utf-8")
    if not path.is_file() or not path.stat().st_size:
        raise OSError("profile_missing_after_write")
    return path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--event-name", default="")
    p.add_argument("--owner-email", required=True)
    p.add_argument("--language", default="en")
    p.add_argument("--timezone", default="")
    p.add_argument("--name", default="")
    p.add_argument("--odoo-locus", default="local")
    args = p.parse_args()
    try:
        path = write_profile(
            event_name=args.event_name,
            owner_email=args.owner_email,
            language=args.language,
            timezone=args.timezone,
            name=args.name,
            odoo_locus=args.odoo_locus,
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
