#!/usr/bin/env python3
"""Render a readable, dependency-free PDF from a Markdown manuscript."""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT = 54
RIGHT = 54
TOP = 54
BOTTOM = 54
BODY_SIZE = 10.5
BODY_LEADING = 13.5


def pdf_escape(text: str) -> bytes:
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text.encode("latin-1", "replace")


def clean_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    return re.sub(r"\s+", " ", text).strip()


def line_style(raw_line: str) -> tuple[str, str, float, float, int]:
    line = raw_line.rstrip()
    stripped = line.strip()
    if not stripped:
        return "", "F1", BODY_SIZE, BODY_LEADING, 0

    match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
    if match:
        level = len(match.group(1))
        size = {1: 15.5, 2: 13.5, 3: 12.0, 4: 11.2}[level]
        leading = size + 5
        return clean_inline(match.group(2)), "F2", size, leading, 0

    if stripped.startswith("|"):
        return stripped, "F3", 7.8, 10.0, 0

    if stripped.startswith("- "):
        return "- " + clean_inline(stripped[2:]), "F1", BODY_SIZE, BODY_LEADING, 12

    numbered = re.match(r"^(\d+)\.\s+(.*)$", stripped)
    if numbered:
        return f"{numbered.group(1)}. {clean_inline(numbered.group(2))}", "F1", BODY_SIZE, BODY_LEADING, 12

    return clean_inline(stripped), "F1", BODY_SIZE, BODY_LEADING, 0


def wrap_line(text: str, font: str, size: float, indent: int) -> list[str]:
    usable = PAGE_WIDTH - LEFT - RIGHT - indent
    width_factor = 0.54 if font != "F3" else 0.60
    max_chars = max(28, int(usable / (size * width_factor)))
    return textwrap.wrap(text, width=max_chars, break_long_words=False, break_on_hyphens=False) or [""]


def markdown_to_draw_ops(markdown: str) -> list[tuple[str, str, float, float, int]]:
    ops: list[tuple[str, str, float, float, int]] = []
    in_fence = False
    for raw in markdown.splitlines():
        if raw.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            ops.append((raw.rstrip(), "F3", 8.2, 10.5, 12))
            continue
        text, font, size, leading, indent = line_style(raw)
        if not text:
            ops.append(("", "F1", BODY_SIZE, 8.0, 0))
            continue
        for i, wrapped in enumerate(wrap_line(text, font, size, indent)):
            continuation_indent = indent if i == 0 else (indent + 12 if indent else 0)
            ops.append((wrapped, font, size, leading, continuation_indent))
        if font == "F2":
            ops.append(("", "F1", BODY_SIZE, 3.0, 0))
    return ops


def paginate(ops: list[tuple[str, str, float, float, int]]) -> list[list[tuple[str, str, float, int, float]]]:
    pages: list[list[tuple[str, str, float, int, float]]] = []
    page: list[tuple[str, str, float, int, float]] = []
    y = PAGE_HEIGHT - TOP
    for text, font, size, leading, indent in ops:
        if y - leading < BOTTOM:
            pages.append(page)
            page = []
            y = PAGE_HEIGHT - TOP
        y -= leading
        if text:
            page.append((text, font, size, indent, y))
    if page:
        pages.append(page)
    return pages


def build_content(page_ops: list[tuple[str, str, float, int, float]], page_num: int, page_count: int) -> bytes:
    chunks: list[bytes] = []
    for text, font, size, indent, y in page_ops:
        chunks.append(
            b"BT /%b %.2f Tf 1 0 0 1 %.2f %.2f Tm (%b) Tj ET\n"
            % (font.encode("ascii"), size, LEFT + indent, y, pdf_escape(text))
        )
    footer = f"{page_num} of {page_count}"
    chunks.append(
        b"BT /F1 8 Tf 1 0 0 1 %.2f 28 Tm (%b) Tj ET\n"
        % (PAGE_WIDTH / 2 - 12, pdf_escape(footer))
    )
    return b"".join(chunks)


def write_pdf(markdown: str, out_path: Path) -> None:
    pages = paginate(markdown_to_draw_ops(markdown))
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    }
    kids = []
    for index, page_ops in enumerate(pages):
        page_id = 6 + index * 2
        content_id = page_id + 1
        kids.append(f"{page_id} 0 R".encode("ascii"))
        content = build_content(page_ops, index + 1, len(pages))
        objects[content_id] = b"<< /Length %d >>\nstream\n%bendstream" % (len(content), content)
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
            + b"/Contents "
            + f"{content_id} 0 R".encode("ascii")
            + b" >>"
        )
    objects[2] = b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count " + str(len(pages)).encode("ascii") + b" >>"

    ordered_ids = sorted(objects)
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {0: 0}
    for obj_id in ordered_ids:
        offsets[obj_id] = len(pdf)
        pdf.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        pdf.extend(objects[obj_id])
        pdf.extend(b"\nendobj\n")
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {max(ordered_ids) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, max(ordered_ids) + 1):
        pdf.extend(f"{offsets.get(obj_id, 0):010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        b"trailer\n<< /Size "
        + str(max(ordered_ids) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_start).encode("ascii")
        + b"\n%%EOF\n"
    )
    out_path.write_bytes(pdf)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    write_pdf(args.input.read_text(encoding="utf-8"), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
