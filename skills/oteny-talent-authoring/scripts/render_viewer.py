#!/usr/bin/env python3
"""render_viewer — a packaged Talent → one self-contained ``index.html`` (Phase 1).

The read-back surface Telegram can't give: open the link and see the whole bundle —
every file listed, Markdown rendered, code/YAML in styled language-tagged blocks, and
a "Download bundle.zip" button. The page is **fully self-contained** (inline CSS, no
external fetch) so it works offline and can't break on a dead CDN, and **all bundle
content is escaped** — a hostile ``</script>`` in a file becomes inert text, never a
live element.

    # after package_talent.py + publishing the zip:
    python3 render_viewer.py --package <export-dir> --zip-url https://drop.oteny.bot/<id>/<slug>.zip
    # writes <export-dir>/index.html — then publish_file that and share the link.

Pure (a package dir + a URL in → an HTML string out), so it is unit-tested offline.
The Markdown renderer is a focused stdlib subset (headings, lists, tables, links,
bold/italic/inline code, fenced + indented code) — enough for a faithful bundle view
with zero dependencies.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

_LANG = {
    ".py": "python", ".sql": "sql", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".sh": "bash", ".toml": "toml", ".cfg": "ini", ".txt": "text", ".md": "markdown",
}


def _lang_for(path: str) -> str:
    return _LANG.get(Path(path).suffix, "text")


# --------------------------------------------------------------------------- #
# Markdown -> HTML (focused, dependency-free, escape-first)                    #
# --------------------------------------------------------------------------- #
def _inline(s: str) -> str:
    """Render inline Markdown on a single line, escaping all literal text first."""
    spans: list[str] = []

    def stash(m):  # protect `code` from escaping/transforms, then restore last
        spans.append(html.escape(m.group(1), quote=False))
        return f"\x00{len(spans) - 1}\x00"

    s = re.sub(r"`([^`]+)`", stash, s)
    s = html.escape(s, quote=False)  # after this no raw HTML can survive

    def link(m):
        text, url = m.group(1), m.group(2)
        # drop unsafe schemes (javascript:, data:) — keep http(s)/mailto/relative/anchor
        if not re.match(r"^(https?:|mailto:|/|#|\.|[A-Za-z0-9_])", url):
            return text
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{text}</a>'

    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w_])_([^_]+)_(?![\w_])", r"<em>\1</em>", s)
    s = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", s)
    return s


def _is_table_sep(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s:\-|]+\s*$", line)) and "-" in line and "|" in line


def _row_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _render_table(header: str, rows: list[str]) -> str:
    head = "".join(f"<th>{_inline(c)}</th>" for c in _row_cells(header))
    body = "".join(
        "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in _row_cells(r)) + "</tr>"
        for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _list_items(lines: list[str], i: int, indent: int) -> tuple[str, int]:
    ordered = bool(re.match(r"^\s*\d+\.\s", lines[i]))
    tag = "ol" if ordered else "ul"
    out = [f"<{tag}>"]
    n = len(lines)
    while i < n:
        m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i])
        if not m:
            break
        cur = len(m.group(1))
        if cur < indent:
            break
        if cur > indent:  # a deeper list belongs to the previous <li>
            nested, i = _list_items(lines, i, cur)
            out[-1] = out[-1][: -len("</li>")] + nested + "</li>"
            continue
        out.append(f"<li>{_inline(m.group(3).strip())}</li>")
        i += 1
    out.append(f"</{tag}>")
    return "".join(out), i


def md_to_html(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        m = re.match(r"^```(\w+)?\s*$", line)
        if m:  # fenced code
            lang = m.group(1) or "text"
            j, buf = i + 1, []
            while j < n and not re.match(r"^```\s*$", lines[j]):
                buf.append(lines[j])
                j += 1
            code = html.escape("\n".join(buf), quote=False)
            out.append(f'<pre><code class="lang-{lang}">{code}</code></pre>')
            i = j + 1
            continue
        if line.strip() == "":
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:  # heading
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2).strip())}</h{lvl}>")
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        if "|" in line and i + 1 < n and _is_table_sep(lines[i + 1]):  # pipe table
            j, rows = i + 2, []
            while j < n and "|" in lines[j] and lines[j].strip():
                rows.append(lines[j])
                j += 1
            out.append(_render_table(line, rows))
            i = j
            continue
        if re.match(r"^>\s?", line):  # blockquote
            buf = []
            while i < n and re.match(r"^>\s?", lines[i]):
                buf.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf))}</blockquote>")
            continue
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):  # list
            indent = len(line) - len(line.lstrip())
            block, i = _list_items(lines, i, indent)
            out.append(block)
            continue
        buf = []  # paragraph
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|```|>|\s*([-*+]|\d+\.)\s)", lines[i]
        ):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{_inline(' '.join(buf))}</p>")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Page assembly                                                                #
# --------------------------------------------------------------------------- #
_CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:#1b1f24;background:#f6f8fa}
@media(prefers-color-scheme:dark){body{color:#e6edf3;background:#0d1117}}
.wrap{max-width:920px;margin:0 auto;padding:24px 16px 64px}
header{border-bottom:1px solid #d0d7de40;padding-bottom:16px;margin-bottom:8px}
h1{margin:0 0 4px;font-size:1.6rem}
.meta{font-size:.85rem;opacity:.75}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.75rem;
  border:1px solid #d0d7de80;margin-left:6px}
.badge.owner{background:#1f883d20;border-color:#1f883d80}
.badge.imported{background:#9a670020;border-color:#9a670080}
.dl{display:inline-block;margin-top:10px;padding:8px 14px;border-radius:8px;
  background:#1f6feb;color:#fff;text-decoration:none;font-weight:600}
.dl-missing{opacity:.6;font-style:italic}
nav{margin:16px 0;padding:12px 16px;border:1px solid #d0d7de40;border-radius:10px;
  background:#ffffff80}
@media(prefers-color-scheme:dark){nav{background:#161b2280}}
nav ul{margin:6px 0 0;padding-left:18px;columns:2;font-size:.9rem}
section{margin:28px 0;overflow-wrap:anywhere}
h2.file{font-size:1rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  background:#d0d7de30;padding:6px 10px;border-radius:6px}
pre{background:#161b22;color:#e6edf3;padding:14px;border-radius:8px;overflow:auto;font-size:.85rem}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
:not(pre)>code{background:#d0d7de40;padding:.1em .35em;border-radius:4px;font-size:.9em}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{border:1px solid #d0d7de60;padding:6px 10px;text-align:left}
blockquote{margin:0;padding:.2em 1em;border-left:4px solid #d0d7de80;opacity:.85}
a{color:#1f6feb}
.bin{opacity:.7;font-style:italic}
""".strip()


def render(*, package_dir, zip_url: str | None = None) -> str:
    package_dir = Path(package_dir)
    manifest = json.loads((package_dir / "manifest.json").read_text())
    slug = manifest["slug"]
    staged = package_dir / slug

    nav, sections = [], []
    for f in manifest["files"]:
        rel = f["path"]
        anchor = "f-" + re.sub(r"[^a-zA-Z0-9]+", "-", rel).strip("-")
        nav.append(f'<li><a href="#{anchor}">{html.escape(rel)}</a></li>')
        if f.get("binary"):
            body = (
                f'<p class="bin">Binary file ({f["bytes"]} bytes) — '
                "open it from the downloaded bundle.</p>"
            )
        else:
            content = (staged / rel).read_text()
            if rel.endswith(".md"):
                body = md_to_html(content)
            else:
                body = (
                    f'<pre><code class="lang-{_lang_for(rel)}">'
                    f"{html.escape(content, quote=False)}</code></pre>"
                )
        sections.append(
            f'<section id="{anchor}"><h2 class="file">{html.escape(rel)}</h2>{body}</section>'
        )

    src = manifest.get("source", "owner")
    badge = f'<span class="badge {html.escape(src)}">{html.escape(src)}</span>'
    if src == "imported":
        badge += '<span class="badge imported">unverified</span>'
    ver = manifest.get("talent_version")
    meta_bits = [f"slug <code>{html.escape(slug)}</code>"]
    if ver:
        meta_bits.append(f"version {html.escape(str(ver))}")
    meta_bits.append(
        "authoring-standard "
        f"{html.escape(str(manifest.get('talent_authoring_standard_version', '?')))}"
    )
    meta_bits.append(f"{len(manifest['files'])} files")
    if zip_url:
        dl = (
            f'<a class="dl" href="{html.escape(zip_url, quote=True)}" '
            'download>Download bundle.zip</a>'
        )
    else:
        dl = '<span class="dl-missing">(publish the zip, then re-render with --zip-url)</span>'

    title = html.escape(manifest.get("display_name") or slug)
    tagline = html.escape(manifest.get("tagline") or "")
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title} — Oteny Talent</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        '<div class="wrap">\n<header>\n'
        f"<h1>{title} {badge}</h1>\n"
        + (f'<p class="meta">{tagline}</p>\n' if tagline else "")
        + f'<p class="meta">{" · ".join(meta_bits)}</p>\n{dl}\n</header>\n'
        f'<nav><strong>Files</strong><ul>{"".join(nav)}</ul></nav>\n'
        + "\n".join(sections)
        + "\n</div>\n</body>\n</html>\n"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render a packaged Talent to a self-contained HTML viewer.")
    ap.add_argument("--package", required=True, help="the export dir from package_talent.py")
    ap.add_argument("--zip-url", help="the published drop URL of bundle.zip (for the download button)")
    ap.add_argument("--out", help="output HTML path (default: <package>/index.html)")
    args = ap.parse_args(argv)
    pkg = Path(args.package)
    out = Path(args.out) if args.out else pkg / "index.html"
    out.write_text(render(package_dir=pkg, zip_url=args.zip_url))
    print(f"Wrote {out} — publish_file it and share the link.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
