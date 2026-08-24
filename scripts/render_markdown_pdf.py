#!/usr/bin/env python3
"""Render a readable PDF from a Markdown manuscript.

Text rendering is dependency-free. Markdown image lines (``![caption](path)``) are
embedded as JPEG XObjects, which needs Pillow; a missing image or a missing Pillow
is reported as a visible placeholder rather than silently dropped, so a figure can
never go missing from a report without the reader seeing it.
"""

from __future__ import annotations

import argparse
import io
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
CAPTION_SIZE = 8.5
CAPTION_LEADING = 11.0
IMAGE_MAX_HEIGHT = 470.0
IMAGE_MAX_PIXELS = 1700
IMAGE_JPEG_QUALITY = 88


# Base-14 Helvetica cannot carry these code points, and latin-1 replacement turns
# them into "?" mid-sentence. Map them to ASCII equivalents instead.
TRANSLITERATIONS = {
    "\u2014": "-", "\u2013": "-", "\u2212": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2192": "->", "\u2190": "<-",
    "\u00d7": "x", "\u2248": "~", "\u2264": "<=", "\u2265": ">=", "\u00b5": "u",
    "\u03bc": "u", "\u0394": "delta ", "\u03c1": "rho", "\u03b1": "alpha",
    "\u03b2": "beta", "\u2020": "+", "\u2713": "yes", "\u2717": "no",
    "\u00b7": "-", "\u00b0": "deg", "\u00a0": " ", "\u2011": "-", "\u2032": "'",
    "\u2033": '"', "\u00ad": "", "\u2009": " ", "\u202f": " ",
}


def transliterate(text: str) -> str:
    for source, target in TRANSLITERATIONS.items():
        text = text.replace(source, target)
    return text


def pdf_escape(text: str) -> bytes:
    text = transliterate(text)
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text.encode("latin-1", "replace")


def clean_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    return re.sub(r"\s+", " ", text).strip()


IMAGE_PATTERN = re.compile(r"^!\[(?P<caption>[^\]]*)\]\((?P<path>[^)]+)\)$")


def load_image(path: Path) -> dict | None:
    """Return JPEG bytes plus pixel dimensions for one image, or None if unusable."""

    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as handle:
            image = handle.convert("RGB")
            if max(image.size) > IMAGE_MAX_PIXELS:
                scale = IMAGE_MAX_PIXELS / max(image.size)
                image = image.resize(
                    (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
                )
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY)
            return {"data": buffer.getvalue(), "width": image.width, "height": image.height}
    except (OSError, ValueError):
        return None


def image_box(pixel_width: int, pixel_height: int) -> tuple[float, float]:
    usable = PAGE_WIDTH - LEFT - RIGHT
    width = usable
    height = pixel_height * (width / pixel_width)
    if height > IMAGE_MAX_HEIGHT:
        height = IMAGE_MAX_HEIGHT
        width = pixel_width * (height / pixel_height)
    return width, height


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


TABLE_MIN_SIZE = 5.6
TABLE_MAX_SIZE = 7.8
COURIER_WIDTH_FACTOR = 0.60


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(set(cell) <= {"-", ":"} and cell for cell in cells)


def format_table(rows: list[str]) -> list[tuple[str, float]]:
    """Lay a markdown table out as padded monospace rows sized to fit the page."""

    parsed = [
        [clean_inline(cell) for cell in row.strip().strip("|").split("|")]
        for row in rows
        if not is_table_separator(row)
    ]
    if not parsed:
        return []
    columns = max(len(row) for row in parsed)
    parsed = [row + [""] * (columns - len(row)) for row in parsed]
    widths = [max(len(row[index]) for row in parsed) for index in range(columns)]

    usable = PAGE_WIDTH - LEFT - RIGHT - 12
    total_chars = sum(widths) + 3 * (columns - 1)
    size = min(TABLE_MAX_SIZE, usable / max(total_chars, 1) / COURIER_WIDTH_FACTOR)
    if size < TABLE_MIN_SIZE:
        # Too wide even at the floor size: shrink the widest columns until it fits.
        size = TABLE_MIN_SIZE
        budget = int(usable / (size * COURIER_WIDTH_FACTOR)) - 3 * (columns - 1)
        while sum(widths) > budget and max(widths) > 6:
            widths[widths.index(max(widths))] -= 1

    lines: list[tuple[str, float]] = []
    for row_index, row in enumerate(parsed):
        cells = []
        for index, cell in enumerate(row):
            width = widths[index]
            cells.append((cell[: width - 1] + "\u2026" if len(cell) > width else cell).ljust(width))
        lines.append(("  ".join(cells).rstrip(), size))
        if row_index == 0:
            lines.append(("  ".join("-" * width for width in widths), size))
    return lines


BLOCK_BREAK = re.compile(r"^(#{1,4}\s|\||-\s|\d+\.\s|!\[|```|>\s|\*\s)")


def merge_wrapped_lines(markdown: str) -> str:
    """Join hard-wrapped source lines into one logical line per paragraph or bullet.

    Markdown treats a single newline as a space, but the renderer lays out one source
    line at a time, which turns every hard wrap in the source into a ragged new line.
    Fenced blocks, tables, headings and image lines keep their own line breaks.
    """

    output: list[str] = []
    pending: list[str] = []
    in_fence = False

    def flush() -> None:
        if pending:
            output.append(" ".join(pending))
            pending.clear()

    for raw in markdown.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
            output.append(raw)
            continue
        if in_fence:
            output.append(raw)
            continue
        if not stripped:
            flush()
            output.append("")
            continue
        if BLOCK_BREAK.match(stripped):
            flush()
            pending.append(stripped)
            continue
        pending.append(stripped)
    flush()
    return "\n".join(output)


def markdown_to_draw_ops(markdown: str, base_dir: Path | None = None) -> list[tuple]:
    ops: list[tuple] = []
    in_fence = False
    table_rows: list[str] = []

    def flush_table() -> None:
        if not table_rows:
            return
        for line, size in format_table(table_rows):
            ops.append((line, "F3", size, size + 2.4, 12, None))
        ops.append(("", "F1", BODY_SIZE, 6.0, 0, None))
        table_rows.clear()

    for raw in merge_wrapped_lines(markdown).splitlines():
        if raw.strip().startswith("```"):
            flush_table()
            in_fence = not in_fence
            continue
        if in_fence:
            ops.append((raw.rstrip(), "F3", 8.2, 10.5, 12, None))
            continue

        if raw.strip().startswith("|"):
            table_rows.append(raw.strip())
            continue
        flush_table()

        image_match = IMAGE_PATTERN.match(raw.strip())
        if image_match:
            raw_path = image_match.group("path").strip()
            caption = clean_inline(image_match.group("caption"))
            resolved = Path(raw_path)
            if not resolved.is_absolute() and base_dir is not None:
                resolved = base_dir / resolved
            payload = load_image(resolved) if resolved.is_file() else None
            if payload is None:
                ops.append((f"[figure not embedded: {raw_path}]", "F3", 8.2, 10.5, 12, None))
                continue
            width, height = image_box(payload["width"], payload["height"])
            payload.update({"box_width": width, "box_height": height})
            ops.append(("", "IMG", 0.0, height + 8.0, 0, payload))
            if caption:
                for _i, wrapped in enumerate(wrap_line(caption, "F1", CAPTION_SIZE, 0)):
                    ops.append((wrapped, "F1", CAPTION_SIZE, CAPTION_LEADING, 0, None))
            ops.append(("", "F1", BODY_SIZE, 10.0, 0, None))
            continue

        text, font, size, leading, indent = line_style(raw)
        if not text:
            ops.append(("", "F1", BODY_SIZE, 8.0, 0, None))
            continue
        for i, wrapped in enumerate(wrap_line(text, font, size, indent)):
            continuation_indent = indent if i == 0 else (indent + 12 if indent else 0)
            ops.append((wrapped, font, size, leading, continuation_indent, None))
        if font == "F2":
            ops.append(("", "F1", BODY_SIZE, 3.0, 0, None))
    flush_table()
    return ops


def paginate(ops: list[tuple]) -> list[list[tuple]]:
    pages: list[list[tuple]] = []
    page: list[tuple] = []
    y = PAGE_HEIGHT - TOP
    for text, font, size, leading, indent, payload in ops:
        if y - leading < BOTTOM:
            pages.append(page)
            page = []
            y = PAGE_HEIGHT - TOP
        y -= leading
        if font == "IMG":
            page.append((text, font, size, indent, y, payload))
        elif text:
            page.append((text, font, size, indent, y, None))
    if page:
        pages.append(page)
    return pages


def build_content(page_ops: list[tuple], page_num: int, page_count: int,
                  image_names: dict[int, str] | None = None) -> bytes:
    chunks: list[bytes] = []
    image_names = image_names or {}
    for position, (text, font, size, indent, y, payload) in enumerate(page_ops):
        if font == "IMG":
            name = image_names.get(position)
            if name is None:
                continue
            width = payload["box_width"]
            height = payload["box_height"]
            left = LEFT + (PAGE_WIDTH - LEFT - RIGHT - width) / 2
            chunks.append(
                b"q %.2f 0 0 %.2f %.2f %.2f cm /%b Do Q\n"
                % (width, height, left, y, name.encode("ascii"))
            )
            continue
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


def write_pdf(markdown: str, out_path: Path, base_dir: Path | None = None) -> None:
    pages = paginate(markdown_to_draw_ops(markdown, base_dir))
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    }
    kids = []
    next_image_id = 6 + len(pages) * 2
    for index, page_ops in enumerate(pages):
        page_id = 6 + index * 2
        content_id = page_id + 1
        kids.append(f"{page_id} 0 R".encode("ascii"))

        image_names: dict[int, str] = {}
        xobject_entries: list[bytes] = []
        for position, op in enumerate(page_ops):
            if op[1] != "IMG":
                continue
            payload = op[5]
            name = f"Im{len(image_names)}"
            image_names[position] = name
            objects[next_image_id] = (
                b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\n"
                b"stream\n" % (payload["width"], payload["height"], len(payload["data"]))
                + payload["data"]
                + b"\nendstream"
            )
            xobject_entries.append(f"/{name} {next_image_id} 0 R".encode("ascii"))
            next_image_id += 1

        content = build_content(page_ops, index + 1, len(pages), image_names)
        objects[content_id] = b"<< /Length %d >>\nstream\n%bendstream" % (len(content), content)
        resources = b"/Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >>"
        if xobject_entries:
            resources += b" /XObject << " + b" ".join(xobject_entries) + b" >>"
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << " + resources + b" >> "
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
    write_pdf(args.input.read_text(encoding="utf-8"), args.output, args.input.resolve().parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
