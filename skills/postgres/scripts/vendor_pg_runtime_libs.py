#!/usr/bin/env python3
"""Put Ubuntu Noble libs next to the theseus PostgreSQL prefix.

The 18.6.0 gnu tarball needs ``libxml2.so.2``. The Hermes parent
does not ship that library. ``libxml2`` then needs ICU 74.
No apt. Fetch two pinned debs and copy only those ``.so`` files
into ``~/postgres/lib``.
"""
from __future__ import annotations

import ctypes
import hashlib
import io
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

XML_URL = (
    "http://security.ubuntu.com/ubuntu/pool/main/libx/libxml2/"
    "libxml2_2.9.14+dfsg-1.3ubuntu3.8_amd64.deb"
)
XML_SHA256 = "bfd07c01d6e5ab3e327f3ca5819409b1914bbfb3f1a016d53e4dabd5f96143bb"
ICU_URL = (
    "http://archive.ubuntu.com/ubuntu/pool/main/i/icu/"
    "libicu74_74.2-1ubuntu3.1_amd64.deb"
)
ICU_SHA256 = "c9a70989678660eed9a1e904c74fa043da8bec8e2036856fc16e31ced79b04f8"

_KEEP_PREFIXES = ("libxml2.so", "libicuuc.so", "libicudata.so")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch(url: str, dest: Path, expect: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and _sha256(dest) == expect:
        return
    urllib.request.urlretrieve(url, dest)
    got = _sha256(dest)
    if got != expect:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"POSTGRES_INSTALL_REFUSED sha256 mismatch for {dest.name}")


def _zstd_decompress(blob: bytes) -> bytes:
    lib = ctypes.CDLL("libzstd.so.1")
    lib.ZSTD_isError.restype = ctypes.c_uint
    lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
    lib.ZSTD_decompress.restype = ctypes.c_size_t
    lib.ZSTD_decompress.argtypes = [
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    src = (ctypes.c_char * len(blob)).from_buffer_copy(blob)
    # Ubuntu debs often omit a content-size in the zstd frame.
    cap = 80 * 1024 * 1024
    out = ctypes.create_string_buffer(cap)
    wrote = lib.ZSTD_decompress(out, cap, src, len(blob))
    if lib.ZSTD_isError(wrote) or wrote == 0:
        raise SystemExit("POSTGRES_INSTALL_REFUSED zstd decompress failed")
    return out.raw[:wrote]


def _data_tar(deb: Path) -> bytes:
    listing = subprocess.check_output(["ar", "t", str(deb)], text=True)
    member = next(
        (line.strip() for line in listing.splitlines() if line.startswith("data.tar")),
        "",
    )
    if not member:
        raise SystemExit(f"POSTGRES_INSTALL_REFUSED no data.tar in {deb.name}")
    blob = subprocess.check_output(["ar", "p", str(deb), member])
    if member.endswith(".zst"):
        return _zstd_decompress(blob)
    if member.endswith(".xz"):
        import lzma

        return lzma.decompress(blob)
    if member.endswith(".gz"):
        import gzip

        return gzip.decompress(blob)
    return blob


def _copy_libs(tar_bytes: bytes, dest_lib: Path) -> list[str]:
    dest_lib.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
        for info in archive.getmembers():
            name = Path(info.name).name
            if not info.isfile() or not name.startswith(_KEEP_PREFIXES):
                continue
            handle = archive.extractfile(info)
            if handle is None:
                continue
            target = dest_lib / name
            target.write_bytes(handle.read())
            target.chmod(0o644)
            copied.append(name)
    return copied


def libs_present(prefix: Path) -> bool:
    lib = prefix / "lib"
    return (lib / "libxml2.so.2").exists() or any(lib.glob("libxml2.so.2*"))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: vendor_pg_runtime_libs.py PREFIX", file=sys.stderr)
        return 2
    prefix = Path(argv[1]).expanduser()
    dest_lib = prefix / "lib"
    if libs_present(prefix):
        print("POSTGRES_RUNTIME_LIBS already")
        return 0
    cache = prefix / ".debs"
    xml_deb = cache / "libxml2_2.9.14+dfsg-1.3ubuntu3.8_amd64.deb"
    icu_deb = cache / "libicu74_74.2-1ubuntu3.1_amd64.deb"
    _fetch(XML_URL, xml_deb, XML_SHA256)
    _fetch(ICU_URL, icu_deb, ICU_SHA256)
    copied: list[str] = []
    for deb in (xml_deb, icu_deb):
        copied.extend(_copy_libs(_data_tar(deb), dest_lib))
    if not any(name.startswith("libxml2.so") for name in copied):
        raise SystemExit("POSTGRES_INSTALL_REFUSED libxml2.so missing after extract")
    # theseus ldd asks for the SONAME, not the full versioned file.
    xml = next(dest_lib.glob("libxml2.so.2.*"), None)
    soname = dest_lib / "libxml2.so.2"
    if xml is not None and not soname.exists():
        soname.symlink_to(xml.name)
    for pattern, soname_name in (
        ("libicuuc.so.74.*", "libicuuc.so.74"),
        ("libicudata.so.74.*", "libicudata.so.74"),
    ):
        real = next(dest_lib.glob(pattern), None)
        link = dest_lib / soname_name
        if real is not None and not link.exists():
            link.symlink_to(real.name)
    print("POSTGRES_RUNTIME_LIBS", " ".join(sorted(copied)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
