"""Operations that stamp text, images, or another document onto every page."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter

from ._draw import draw_image, draw_text
from ..pages import output_path
from ..registry import InputSlot, Param, register

_IMAGE_FORMATS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")

_MARGIN = 24.0


@register(
    id="page_numbers",
    label="Page numbers",
    category="Annotate",
    summary="Stamp a page number onto every page.",
    params=(
        Param(
            "position",
            "choice",
            "Position",
            default="bottom-center",
            choices=(
                "bottom-center",
                "bottom-right",
                "bottom-left",
                "top-center",
                "top-right",
                "top-left",
            ),
            required=True,
        ),
        Param("start", "int", "Start at", default=1, minimum=0),
        Param("font_size", "int", "Font size", default=10, minimum=4, maximum=72),
        Param(
            "format",
            "str",
            "Format",
            default="{n}",
            help="{n} is the page number, {total} is the page count",
        ),
    ),
)
def page_numbers(
    sources: list[Path],
    out_dir: Path,
    position: str = "bottom-center",
    start: int = 1,
    font_size: int = 10,
    format: str = "{n}",
) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    total = len(writer.pages)
    for index, page in enumerate(writer.pages):
        label = format.format(n=start + index, total=total)
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        # ponytail: Helvetica average-glyph-width estimate, no real font metrics table
        text_width = font_size * 0.5 * len(label)
        x = {
            "bottom-left": _MARGIN,
            "top-left": _MARGIN,
            "bottom-center": (width - text_width) / 2,
            "top-center": (width - text_width) / 2,
            "bottom-right": width - _MARGIN - text_width,
            "top-right": width - _MARGIN - text_width,
        }[position]
        y = _MARGIN if position.startswith("bottom") else height - _MARGIN - font_size
        draw_text(writer, page, label, x, y, size=font_size)
    target = output_path(out_dir, f"{src.stem}-numbered")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="watermark_text",
    label="Text watermark",
    category="Annotate",
    summary="Stamp a translucent, rotated line of text across every page.",
    params=(
        Param("text", "str", "Watermark text", default="DRAFT", required=True),
        Param("font_size", "int", "Font size", default=48, minimum=6, maximum=200),
        Param("opacity", "float", "Opacity", default=0.25, minimum=0.05, maximum=1.0),
        Param("angle", "float", "Rotation (degrees)", default=45.0, minimum=-180, maximum=180),
    ),
)
def watermark_text(
    sources: list[Path],
    out_dir: Path,
    text: str = "DRAFT",
    font_size: int = 48,
    opacity: float = 0.25,
    angle: float = 45.0,
) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for page in writer.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        draw_text(
            writer,
            page,
            text,
            0,
            0,
            size=font_size,
            opacity=opacity,
            rgb=(0.5, 0.5, 0.5),
            angle=angle,
            center=(width / 2, height / 2),
        )
    target = output_path(out_dir, f"{src.stem}-watermarked")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="watermark_image",
    label="Image watermark / stamp",
    category="Annotate",
    summary="Stamp an image onto every page of one or more PDFs, scaled and centred.",
    inputs="many",
    outputs="many",
    input_slots=(
        InputSlot("pdfs", "PDF files", arity="many", formats=(".pdf",)),
        InputSlot("image", "Watermark image", arity="one", formats=_IMAGE_FORMATS),
    ),
    params=(
        Param("scale", "float", "Fraction of page width", default=0.5, minimum=0.05, maximum=1.0),
        Param("opacity", "float", "Opacity", default=1.0, minimum=0.05, maximum=1.0),
    ),
)
def watermark_image(
    sources: list[Path], out_dir: Path, scale: float = 0.5, opacity: float = 1.0
) -> list[Path]:
    # ponytail: role is decided by file extension, not by argument position --
    # works the same whether sources come from typed GUI slots or a plain CLI list.
    images = [p for p in sources if p.suffix.lower() in _IMAGE_FORMATS]
    pdfs = [p for p in sources if p.suffix.lower() not in _IMAGE_FORMATS]
    if len(images) != 1:
        raise ValueError("Image watermark needs exactly one image file.")
    if not pdfs:
        raise ValueError("Image watermark needs at least one PDF file.")
    image_src = images[0]
    written: list[Path] = []
    with Image.open(image_src) as image:
        image.load()
        for pdf_src in pdfs:
            reader = PdfReader(str(pdf_src))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            for page in writer.pages:
                width, height = float(page.mediabox.width), float(page.mediabox.height)
                w = width * scale
                h = w * image.height / image.width
                draw_image(
                    writer, page, image, (width - w) / 2, (height - h) / 2, w, h, opacity=opacity
                )
            target = output_path(out_dir, f"{pdf_src.stem}-stamped")
            with target.open("wb") as fh:
                writer.write(fh)
            written.append(target)
    return written


@register(
    id="overlay",
    label="Overlay / underlay two PDFs",
    category="Annotate",
    summary="Merge a second PDF onto every page, in front of or behind the original content.",
    inputs="many",
    params=(
        Param("mode", "choice", "Placement", default="over", choices=("over", "under"), required=True),
    ),
)
def overlay(sources: list[Path], out_dir: Path, mode: str = "over") -> list[Path]:
    if len(sources) != 2:
        raise ValueError("Overlay takes exactly two files: the base PDF and the one to merge onto it.")
    base_src, overlay_src = sources
    base = PdfReader(str(base_src))
    over_pages = PdfReader(str(overlay_src)).pages
    writer = PdfWriter()
    for page in base.pages:
        writer.add_page(page)
    for index, page in enumerate(writer.pages):
        if index < len(over_pages):
            page.merge_page(over_pages[index], over=(mode == "over"))
    target = output_path(out_dir, f"{base_src.stem}-overlaid")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]
