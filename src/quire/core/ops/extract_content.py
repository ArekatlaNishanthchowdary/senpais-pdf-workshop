"""Operations that pull content out of a PDF: images and text."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader

from ..pages import output_path
from ..registry import register


@register(
    id="extract_images",
    label="Extract embedded images",
    category="Extract",
    summary="Save every raster image embedded in the document to disk.",
    outputs="many",
)
def extract_images(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    written = []
    for page_index, page in enumerate(reader.pages, start=1):
        for image in page.images:
            stem = f"{src.stem}-p{page_index}-{Path(image.name).stem}"
            suffix = Path(image.name).suffix or ".png"
            target = output_path(out_dir, stem, suffix)
            target.write_bytes(image.data)
            written.append(target)
    if not written:
        raise ValueError("No embedded images found.")
    return written


@register(
    id="extract_text",
    label="Extract plain text",
    category="Extract",
    summary="Save the readable text of the document to a .txt file.",
)
def extract_text(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    text = "\n\n".join(page.extract_text() for page in reader.pages)
    target = output_path(out_dir, f"{src.stem}-text", ".txt")
    target.write_text(text, encoding="utf-8")
    return [target]


@register(
    id="pdf_to_xml",
    label="PDF to XML",
    category="Extract",
    summary="Dump each page's text into a simple <document><page> XML structure.",
)
def pdf_to_xml(sources: list[Path], out_dir: Path) -> list[Path]:
    # ponytail: a self-defined schema, not a reconstruction of any Office/tagged-PDF
    # XML format -- structured text extraction, not a layout-fidelity conversion.
    src = sources[0]
    reader = PdfReader(str(src))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<document>"]
    for index, page in enumerate(reader.pages, start=1):
        parts.append(f'  <page number="{index}">')
        parts.append(f"    <text>{escape(page.extract_text() or '')}</text>")
        parts.append("  </page>")
    parts.append("</document>")
    target = output_path(out_dir, f"{src.stem}", ".xml")
    target.write_text("\n".join(parts), encoding="utf-8")
    return [target]
