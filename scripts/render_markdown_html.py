#!/usr/bin/env python3
"""Render a self-contained HTML page from a Markdown report.

Dependency-free and deterministic, and a sibling of ``render_markdown_pdf.py``: the
same report can be read as PDF or in a browser without a second source of truth.
Figures referenced with ``![caption](path)`` are inlined as base64 data URIs so the
file can be opened or sent anywhere, and a missing figure is rendered as a visible
placeholder rather than silently dropped.
"""

from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import re
from pathlib import Path

CSS = """
:root {
  --ink: #16181d;
  --muted: #5b6270;
  --rule: #d9dde5;
  --accent: #7a1f2b;
  --code-bg: #f4f5f8;
  --table-head: #f0f2f6;
}
* { box-sizing: border-box; }
body {
  margin: 0 auto;
  max-width: 54rem;
  padding: 2.5rem 1.5rem 5rem;
  color: var(--ink);
  background: #fff;
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  -webkit-text-size-adjust: 100%;
}
h1 { font-size: 1.85rem; line-height: 1.25; margin: 0 0 1rem; letter-spacing: -0.01em; }
h2 {
  font-size: 1.3rem; margin: 2.75rem 0 0.85rem; padding-bottom: 0.35rem;
  border-bottom: 2px solid var(--rule);
}
h3 { font-size: 1.05rem; margin: 1.9rem 0 0.6rem; color: var(--accent); }
p { margin: 0 0 0.9rem; }
ul { margin: 0 0 1rem; padding-left: 1.25rem; }
li { margin: 0 0 0.4rem; }
code {
  font: 0.86em/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: var(--code-bg); padding: 0.1em 0.35em; border-radius: 3px;
}
pre {
  background: var(--code-bg); border: 1px solid var(--rule); border-radius: 6px;
  padding: 0.9rem 1rem; overflow-x: auto; margin: 0 0 1.2rem;
}
pre code { background: none; padding: 0; font-size: 0.82rem; }
.table-wrap { overflow-x: auto; margin: 0 0 1.4rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.84rem; }
th, td {
  border: 1px solid var(--rule); padding: 0.4rem 0.55rem;
  text-align: left; vertical-align: top; overflow-wrap: anywhere;
}
td a { overflow-wrap: anywhere; }
th { background: var(--table-head); font-weight: 600; }
tbody tr:nth-child(even) { background: #fafbfc; }
td code { font-size: 0.95em; }
figure { margin: 1.6rem 0 2rem; }
figure img {
  width: 100%; height: auto; display: block;
  border: 1px solid var(--rule); border-radius: 4px; background: #fff;
}
figcaption { margin-top: 0.5rem; font-size: 0.82rem; color: var(--muted); line-height: 1.45; }
.missing-figure {
  border: 1px dashed var(--accent); border-radius: 4px; padding: 1rem;
  color: var(--accent); font-size: 0.85rem; background: #fdf6f7;
}
a { color: var(--accent); }
hr { border: 0; border-top: 1px solid var(--rule); margin: 2rem 0; }
@media print {
  body { max-width: none; padding: 0; font-size: 11pt; }
  h2 { page-break-after: avoid; }
  figure, tr, pre { page-break-inside: avoid; }
}
"""

IMAGE_RE = re.compile(r"^!\[(?P<caption>[^\]]*)\]\((?P<path>[^)]+)\)\s*$")
HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*)$")
TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:\-|]+\|$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>.*)$")


def inline(text: str) -> str:
    """Convert inline Markdown to HTML, escaping everything else."""

    placeholders: list[str] = []

    def stash(markup: str) -> str:
        placeholders.append(markup)
        return f"\x00{len(placeholders) - 1}\x00"

    # Code spans first: their contents must not be reinterpreted as emphasis.
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: stash(
            f'<a href="{html.escape(m.group(2), quote=True)}">{html.escape(m.group(1))}</a>'
        ),
        text,
    )
    text = html.escape(text)
    # Bare URLs are common in provenance tables; Markdown links are already stashed, so
    # this cannot double-wrap one. Trailing sentence punctuation stays outside the link.
    # The ellipsis is excluded so a clipped URL is left as plain text: a truncated href
    # would be a broken link dressed up as a working one.
    text = re.sub(
        r"(?<![\w@])(https?://[^\s<>\"\u2026]+?)([.,;:)\]]*)(?=\s|$)",
        lambda m: stash(f'<a href="{m.group(1)}">{m.group(1)}</a>') + m.group(2),
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
    for index, markup in enumerate(placeholders):
        text = text.replace(f"\x00{index}\x00", markup)
    return text


def data_uri(path: Path) -> str | None:
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def render_table(rows: list[str]) -> str:
    def cells(row: str) -> list[str]:
        return [cell.strip() for cell in row.strip().strip("|").split("|")]

    header, body = cells(rows[0]), [cells(row) for row in rows[2:]]
    width = len(header)
    out = ['<div class="table-wrap"><table>', "<thead><tr>"]
    out += [f"<th>{inline(cell)}</th>" for cell in header]
    out.append("</tr></thead><tbody>")
    for row in body:
        padded = (row + [""] * width)[:width]
        out.append("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in padded) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def markdown_to_html(markdown: str, base_dir: Path) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    bullets: list[str] = []
    table: list[str] = []
    code: list[str] | None = None
    code_language = ""

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{inline(item)}</li>" for item in bullets) + "</ul>")
            bullets.clear()

    def flush_table() -> None:
        if table:
            # A table needs a header row, a separator, and at least the separator's shape.
            out.append(render_table(table) if len(table) >= 2 else "<p>" + inline(table[0]) + "</p>")
            table.clear()

    def flush_all() -> None:
        flush_paragraph()
        flush_bullets()
        flush_table()

    for raw_line in lines:
        line = raw_line.rstrip()

        if code is not None:
            if line.strip().startswith("```"):
                language = html.escape(code_language, quote=True)
                out.append(
                    f'<pre><code class="language-{language}">'
                    + html.escape("\n".join(code))
                    + "</code></pre>"
                )
                code = None
            else:
                code.append(raw_line)
            continue

        if line.strip().startswith("```"):
            flush_all()
            code = []
            code_language = line.strip().strip("`").strip()
            continue

        if not line.strip():
            flush_all()
            continue

        image = IMAGE_RE.match(line)
        if image:
            flush_all()
            caption = image.group("caption")
            path = (base_dir / image.group("path")).resolve()
            uri = data_uri(path)
            if uri is None:
                out.append(
                    '<figure><div class="missing-figure">Figure not found at '
                    f"<code>{html.escape(image.group('path'))}</code>. It is reported here rather than "
                    "dropped, so a missing figure cannot pass unnoticed.</div>"
                    f"<figcaption>{inline(caption)}</figcaption></figure>"
                )
            else:
                out.append(
                    f'<figure><img alt="{html.escape(caption, quote=True)}" src="{uri}">'
                    f"<figcaption>{inline(caption)}</figcaption></figure>"
                )
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_all()
            level = len(heading.group("hashes"))
            out.append(f"<h{level}>{inline(heading.group('text'))}</h{level}>")
            continue

        if line.strip() in {"---", "***", "___"} and not table:
            flush_all()
            out.append("<hr>")
            continue

        if line.lstrip().startswith("|"):
            flush_paragraph()
            flush_bullets()
            table.append(line.strip())
            continue
        flush_table()

        bullet = BULLET_RE.match(line)
        if bullet:
            flush_paragraph()
            bullets.append(bullet.group("text"))
            continue
        flush_bullets()

        paragraph.append(line.strip())

    if code is not None:  # unterminated fence: keep the content visible
        out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
    flush_all()
    return "\n".join(out)


def write_html(markdown_path: Path, out_path: Path) -> Path:
    markdown = markdown_path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.*)$", markdown, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else markdown_path.stem
    body = markdown_to_html(markdown, markdown_path.parent)
    page = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f"{body}\n</body>\n</html>\n"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown")
    parser.add_argument("html")
    args = parser.parse_args()
    path = write_html(Path(args.markdown), Path(args.html))
    print(f"[html] wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
