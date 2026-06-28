"""Validate every shipped ``teaser.yaml`` against the sample-chat schema.

A *teaser* is the believable sample conversation rendered on a Talent's storefront
landing (authored shape: ``skills/talent-authoring-standard/references/store-presentation.md``).
It is consumed by the Oteny seeder's canonical validator
(``hermeshost.talent_teaser.validate_teaser``) — which lives in the control-plane repo, so a
malformed teaser would otherwise only blow up at seed time, never in this bundle's CI. This
test re-implements the same structural invariants (stdlib + PyYAML only, no control-plane
import) so a dangling member reference, a media turn missing ``alt``, an empty card, or a bad
role/colour fails *here*. Keep it in sync with the documented schema above.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from _talents import CATALOG

# The named avatar palette a "them" member may pin (else the render assigns one by index).
_COLORS = {"maya", "priya", "sky", "rose", "sage", "plum"}
_ROLES = {"me", "bot", "them"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "x"


def _member_key(raw: dict, role: str) -> str:
    if raw.get("key"):
        return str(raw["key"])
    return role if role in ("me", "bot") else _slug(str(raw.get("name") or ""))


def validate_teaser(raw: object) -> None:
    """Raise ``AssertionError`` with a precise message on any schema violation.

    Mirrors the seed-time authority (``hermeshost.talent_teaser.validate_teaser``): a
    believable teaser needs a title, declared members with unique keys, and turns that each
    reference a declared member + carry content; every media turn carries the required ``alt``.
    """
    assert isinstance(raw, dict), "teaser must be a mapping"
    raw = raw.get("teaser", raw)
    assert str(raw.get("title") or "").strip(), "teaser needs a non-empty 'title'"

    members = raw.get("members")
    assert isinstance(members, list) and members, "teaser needs a non-empty 'members' list"
    keys: list[str] = []
    for i, m in enumerate(members):
        assert isinstance(m, dict) and str(m.get("name") or "").strip(), (
            f"member #{i} must be a mapping with a non-empty name")
        role = m.get("role") or "them"
        assert role in _ROLES, f"member {m.get('name')!r} has unknown role {role!r}"
        color = m.get("color")
        assert not color or color in _COLORS, (
            f"member {m.get('name')!r} colour {color!r} not in palette {sorted(_COLORS)}")
        keys.append(_member_key(m, role))
    assert len(set(keys)) == len(keys), f"member keys must be unique: {keys}"

    turns = raw.get("turns")
    assert isinstance(turns, list) and turns, "teaser needs a non-empty 'turns' list"
    keyset = set(keys)
    for i, t in enumerate(turns):
        assert isinstance(t, dict), f"turn #{i} must be a mapping"
        assert t.get("from") in keyset, (
            f"turn #{i} 'from'={t.get('from')!r} is not a declared member key {sorted(keyset)}")
        has_content = False
        if t.get("text"):
            has_content = True
        if t.get("card") is not None:
            _validate_card(t["card"], i)
            has_content = True
        for kind in ("image", "video"):
            if t.get(kind) is not None:
                _validate_media(t, kind, i)
                has_content = True
        assert has_content, f"turn #{i} has no content (need text/card/image/video)"


def _validate_card(card: object, i: int) -> None:
    assert isinstance(card, dict), f"turn #{i} card must be a mapping"
    lines = card.get("lines")
    assert isinstance(lines, list) and lines, f"turn #{i} card needs a non-empty 'lines' list"
    for ln in lines:
        if isinstance(ln, dict):
            assert str(ln.get("text") or "").strip(), f"turn #{i} card line missing 'text'"
        else:
            assert str(ln).strip(), f"turn #{i} card line is empty"


def _validate_media(turn: dict, kind: str, i: int) -> None:
    spec = turn[kind]
    if isinstance(spec, str):
        src, alt = spec, turn.get("alt")
    elif isinstance(spec, dict):
        src, alt = spec.get("src"), spec.get("alt", turn.get("alt"))
    else:
        raise AssertionError(f"turn #{i} {kind} must be a path string or a mapping")
    assert src, f"turn #{i} {kind} has no 'src'"
    assert str(alt or "").strip(), (
        f"turn #{i} {kind} requires a non-empty 'alt' (accessibility floor)")


def _shipped_teasers() -> list[Path]:
    return sorted(CATALOG.glob("*/teaser.yaml"))


@pytest.mark.parametrize("teaser_path", _shipped_teasers(), ids=lambda p: p.parent.name)
def test_shipped_teaser_is_valid(teaser_path: Path) -> None:
    validate_teaser(yaml.safe_load(teaser_path.read_text()))


def test_repo_ships_at_least_one_teaser() -> None:
    # Guards the parametrize above from silently passing on zero teasers.
    assert _shipped_teasers(), "no skills/*/teaser.yaml found"


# --- the validator actually rejects the bug classes (so the gate has teeth) --- #

_GOOD = {
    "teaser": {
        "title": "T", "members": [
            {"key": "me", "name": "You", "role": "me"},
            {"key": "bot", "name": "OtenyBot", "role": "bot"},
        ],
        "turns": [{"from": "me", "text": "hi"}],
    }
}


def test_rejects_dangling_member_reference() -> None:
    bad = {"teaser": {**_GOOD["teaser"], "turns": [{"from": "ghost", "text": "hi"}]}}
    with pytest.raises(AssertionError, match="not a declared member"):
        validate_teaser(bad)


def test_rejects_media_turn_without_alt() -> None:
    bad = {"teaser": {**_GOOD["teaser"], "turns": [{"from": "me", "image": "x.png"}]}}
    with pytest.raises(AssertionError, match="requires a non-empty 'alt'"):
        validate_teaser(bad)


def test_rejects_empty_card() -> None:
    bad = {"teaser": {**_GOOD["teaser"], "turns": [{"from": "me", "card": {"lines": []}}]}}
    with pytest.raises(AssertionError, match="non-empty 'lines'"):
        validate_teaser(bad)


def test_rejects_unknown_palette_colour() -> None:
    bad = {"teaser": {**_GOOD["teaser"],
                      "members": [*_GOOD["teaser"]["members"],
                                  {"key": "x", "name": "X", "color": "neon"}]}}
    with pytest.raises(AssertionError, match="palette"):
        validate_teaser(bad)


def test_rejects_contentless_turn() -> None:
    bad = {"teaser": {**_GOOD["teaser"], "turns": [{"from": "me", "at": "9:00"}]}}
    with pytest.raises(AssertionError, match="no content"):
        validate_teaser(bad)
