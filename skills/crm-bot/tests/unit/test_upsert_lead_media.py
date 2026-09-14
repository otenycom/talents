"""upsert_lead.py's avatar-and-media behavior (plan §1 "Script-owned media").

A photo in ``media`` writes the person partner's ``image_1920``; every media
item still attaches to the lead's chatter; a missing/unreadable file records
an error and never aborts the rest of the capture; the company partner's
image is never touched.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "upsert_lead.py"


def _load():
    spec = importlib.util.spec_from_file_location("crm_upsert_lead_media_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class _FakeRpc:
    """Duck-types the two ``odoo_rpc.OdooRPC`` calls ``attach_media`` makes,
    plus the ``res.partner`` read ``_partner_has_avatar`` issues — no network,
    no community client, so this stays a pure unit test of the media logic."""

    def __init__(self, has_avatar: bool = False):
        self._has_avatar = has_avatar
        self.avatar_calls: list[tuple[int, str]] = []
        self.attach_calls: list[tuple[int, str, str | None]] = []

    def call(self, model, method, args=None, kwargs=None):
        if model == "res.partner" and method == "read":
            return [{"image_1920": "existing-b64" if self._has_avatar else False}]
        raise AssertionError(f"unexpected {model}.{method}")

    def set_partner_avatar(self, partner_id: int, path: str) -> None:
        if not Path(path).is_file():
            raise FileNotFoundError(f"media file missing: {path}")
        self.avatar_calls.append((partner_id, path))

    def attach_file(self, lead_id: int, path: str, name: str | None = None):
        if not Path(path).is_file():
            raise FileNotFoundError(f"media file missing: {path}")
        self.attach_calls.append((lead_id, path, name))
        return 900


def test_is_photo_media_matches_label_or_image_suffix():
    mod = _load()
    assert mod._is_photo_media({"label": "badge photo", "path": "x.bin"}) is True
    assert mod._is_photo_media({"label": "", "path": "img.png"}) is True
    assert mod._is_photo_media({"label": "voice note booth", "path": "clip.m4a"}) is False
    assert mod._is_photo_media({"label": "", "path": "clip.m4a"}) is False


def test_partner_has_avatar_uses_bin_size_context():
    mod = _load()
    calls: list[dict] = []

    class _Rpc:
        def call(self, model, method, args=None, kwargs=None):
            calls.append({"model": model, "method": method, "kwargs": kwargs})
            return [{"image_1920": "x"}]

    assert mod._partner_has_avatar(_Rpc(), 10) is True
    assert calls[0]["kwargs"]["context"] == {"bin_size": True}


def test_attach_media_sets_avatar_from_photo_on_empty_partner(tmp_path):
    mod = _load()
    photo = tmp_path / "img_d700fa87.jpg"
    photo.write_bytes(b"fake-jpeg-bytes")
    rpc = _FakeRpc(has_avatar=False)
    avatar_set, attached, errors = mod.attach_media(
        rpc, lead_id=3, partner_id=39, company_id=None,
        media=[{"path": str(photo), "label": "photo of Kajal"}],
        correction=False,
    )
    assert avatar_set is True
    assert attached == ["img_d700fa87.jpg"]
    assert errors == []
    assert rpc.avatar_calls == [(39, str(photo))]
    assert rpc.attach_calls == [(3, str(photo), "photo of Kajal")]


def test_attach_media_does_not_overwrite_avatar_without_correction(tmp_path):
    mod = _load()
    photo = tmp_path / "img_2.jpg"
    photo.write_bytes(b"fake-jpeg-bytes")
    rpc = _FakeRpc(has_avatar=True)
    avatar_set, attached, errors = mod.attach_media(
        rpc, lead_id=3, partner_id=39, company_id=None,
        media=[{"path": str(photo), "label": "photo"}],
        correction=False,
    )
    assert avatar_set is False
    assert rpc.avatar_calls == []
    assert attached == ["img_2.jpg"]  # still attaches to chatter regardless
    assert errors == []


def test_attach_media_correction_replaces_existing_avatar(tmp_path):
    mod = _load()
    photo = tmp_path / "img_3.jpg"
    photo.write_bytes(b"fake-jpeg-bytes")
    rpc = _FakeRpc(has_avatar=True)
    avatar_set, attached, errors = mod.attach_media(
        rpc, lead_id=3, partner_id=39, company_id=None,
        media=[{"path": str(photo), "label": "photo"}],
        correction=True,
    )
    assert avatar_set is True
    assert rpc.avatar_calls == [(39, str(photo))]


def test_attach_media_never_sets_avatar_on_company_partner(tmp_path):
    """Image bytes stay on the person, never the company placeholder."""
    mod = _load()
    photo = tmp_path / "logo.jpg"
    photo.write_bytes(b"fake-jpeg-bytes")
    rpc = _FakeRpc(has_avatar=False)
    avatar_set, attached, errors = mod.attach_media(
        rpc, lead_id=3, partner_id=20, company_id=20,
        media=[{"path": str(photo), "label": "photo"}],
        correction=False,
    )
    assert avatar_set is False
    assert rpc.avatar_calls == []
    assert attached == ["logo.jpg"]


def test_attach_media_audio_file_attaches_but_never_sets_avatar(tmp_path):
    mod = _load()
    audio = tmp_path / "audio_b6290fbc4140.m4a"
    audio.write_bytes(b"fake-audio-bytes")
    rpc = _FakeRpc(has_avatar=False)
    avatar_set, attached, errors = mod.attach_media(
        rpc, lead_id=3, partner_id=39, company_id=None,
        media=[{"path": str(audio), "label": "voice note booth"}],
        correction=False,
    )
    assert avatar_set is False
    assert attached == ["audio_b6290fbc4140.m4a"]
    assert errors == []


def test_attach_media_missing_file_does_not_abort_the_rest(tmp_path):
    mod = _load()
    good_photo = tmp_path / "good.jpg"
    good_photo.write_bytes(b"fake-jpeg-bytes")
    missing = str(tmp_path / "missing.jpg")
    rpc = _FakeRpc(has_avatar=False)
    avatar_set, attached, errors = mod.attach_media(
        rpc, lead_id=3, partner_id=39, company_id=None,
        media=[
            {"path": missing, "label": "photo"},
            {"path": str(good_photo), "label": "photo"},
        ],
        correction=False,
    )
    # the missing file fails both the avatar write and the chatter attach,
    # but the second (good) file still lands both — one bad path never loses
    # the rest of the capture.
    assert avatar_set is True
    assert attached == ["good.jpg"]
    assert len(errors) == 2
    assert all("missing.jpg" in e for e in errors)


def test_attach_media_no_media_is_a_no_op():
    mod = _load()
    rpc = _FakeRpc(has_avatar=False)
    avatar_set, attached, errors = mod.attach_media(
        rpc, lead_id=3, partner_id=39, company_id=None, media=[], correction=False,
    )
    assert (avatar_set, attached, errors) == (False, [], [])
