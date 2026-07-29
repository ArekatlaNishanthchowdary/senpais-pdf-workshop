"""Conversions between PDF pages and raster images, via pypdfium2 + Pillow."""

from __future__ import annotations

import base64
import io
import textwrap
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfWriter

from ._draw import draw_image, draw_text
from ..pages import output_path
from ..registry import Param, register

_PAGE_W, _PAGE_H = 595.0, 842.0
_MARGIN = 48.0


@register(
    id="pdf_to_image",
    label="PDF to images",
    category="Convert",
    summary="Render every page to a JPG or PNG image.",
    outputs="many",
    params=(
        Param("format", "choice", "Format", default="PNG", choices=("PNG", "JPG"), required=True),
        Param("dpi", "int", "Resolution (DPI)", default=150, minimum=36, maximum=600),
    ),
)
def pdf_to_image(
    sources: list[Path], out_dir: Path, format: str = "PNG", dpi: int = 150
) -> list[Path]:
    src = sources[0]
    pdf = pdfium.PdfDocument(str(src))
    ext = ".png" if format == "PNG" else ".jpg"
    width = len(str(len(pdf)))
    written = []
    for index, page in enumerate(pdf, start=1):
        image = page.render(scale=dpi / 72).to_pil()
        if format == "JPG":
            image = image.convert("RGB")
        target = output_path(out_dir, f"{src.stem}-{index:0{width}d}", ext)
        image.save(target)
        written.append(target)
    return written


@register(
    id="images_to_pdf",
    label="Images to PDF",
    category="Convert",
    summary="Combine one or more images into a single PDF, one page each.",
    inputs="many",
    input_formats=(".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"),
    params=(Param("name", "str", "Output name", default="images", help="Without .pdf"),),
)
def images_to_pdf(sources: list[Path], out_dir: Path, name: str = "images") -> list[Path]:
    images = []
    for src in sources:
        with Image.open(src) as im:
            images.append(im.convert("RGB"))
    target = output_path(out_dir, name or "images")
    images[0].save(target, "PDF", save_all=True, append_images=images[1:])
    return [target]


@register(
    id="grayscale",
    label="Grayscale conversion",
    category="Convert",
    summary="Rasterize every page and redraw it in grayscale.",
    params=(Param("dpi", "int", "Resolution (DPI)", default=200, minimum=72, maximum=600),),
)
def grayscale(sources: list[Path], out_dir: Path, dpi: int = 200) -> list[Path]:
    src = sources[0]
    pdf = pdfium.PdfDocument(str(src))
    writer = PdfWriter()
    # ponytail: rasterizes each page then redraws it as a grayscale image --
    # loses vector precision and selectable text, but is the simplest reliable
    # way to guarantee grayscale output across arbitrary color content.
    for page in pdf:
        width_pt, height_pt = page.get_size()
        image = page.render(scale=dpi / 72).to_pil().convert("L")
        out_page = writer.add_blank_page(width=width_pt, height=height_pt)
        draw_image(writer, out_page, image, 0, 0, width_pt, height_pt)
    target = output_path(out_dir, f"{src.stem}-grayscale")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="text_to_pdf",
    label="Text file to PDF",
    category="Convert",
    summary="Lay out a plain text file as a paginated PDF.",
    input_formats=(".txt",),
    params=(Param("font_size", "int", "Font size", default=11, minimum=6, maximum=36),),
)
def text_to_pdf(sources: list[Path], out_dir: Path, font_size: int = 11) -> list[Path]:
    src = sources[0]
    # Helvetica has no embedded metrics table here, so text is limited to what
    # latin-1 can represent -- unencodable characters are replaced, not crashed on.
    raw = src.read_text(encoding="utf-8", errors="replace")
    # ponytail: Helvetica average-glyph-width estimate, same heuristic as page_numbers
    chars_per_line = max(10, int((_PAGE_W - 2 * _MARGIN) / (font_size * 0.5)))
    lines: list[str] = []
    for raw_line in raw.splitlines() or [""]:
        safe_line = raw_line.encode("latin-1", errors="replace").decode("latin-1")
        lines.extend(textwrap.wrap(safe_line, chars_per_line) or [""])

    line_height = font_size * 1.4
    lines_per_page = max(1, int((_PAGE_H - 2 * _MARGIN) / line_height))
    writer = PdfWriter()
    for start in range(0, len(lines), lines_per_page):
        page = writer.add_blank_page(width=_PAGE_W, height=_PAGE_H)
        for i, line in enumerate(lines[start : start + lines_per_page]):
            if line:
                y = _PAGE_H - _MARGIN - (i + 1) * line_height
                draw_text(writer, page, line, _MARGIN, y, size=font_size)
    if not writer.pages:
        writer.add_blank_page(width=_PAGE_W, height=_PAGE_H)
    target = output_path(out_dir, src.stem)
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="pdf_to_web",
    label="PDF to web page",
    category="Convert",
    summary="Render every page as an image and pack them into one self-contained HTML file.",
    params=(Param("dpi", "int", "Resolution (DPI)", default=120, minimum=36, maximum=300),),
)
def pdf_to_web(sources: list[Path], out_dir: Path, dpi: int = 120) -> list[Path]:
    # ponytail: rasterized pages embedded as base64 PNGs -- no selectable text or
    # real reflow, but self-contained (no external assets) with no HTML/CSS
    # layout engine needed to reconstruct the document's structure.
    src = sources[0]
    pdf = pdfium.PdfDocument(str(src))
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{src.stem}</title>"
        "<style>body{margin:0;background:#525659;display:flex;flex-direction:column;"
        "align-items:center;gap:16px;padding:16px}img{max-width:100%;"
        "box-shadow:0 2px 8px rgba(0,0,0,.4)}</style></head><body>"
    ]
    for page in pdf:
        image = page.render(scale=dpi / 72).to_pil().convert("RGB")
        buf = io.BytesIO()
        image.save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        parts.append(f"<img src='data:image/png;base64,{b64}'>")
    parts.append("</body></html>")
    target = output_path(out_dir, src.stem, ".html")
    target.write_text("".join(parts), encoding="utf-8")
    return [target]
