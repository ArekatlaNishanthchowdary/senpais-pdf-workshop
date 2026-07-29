"""Operations for embedded file attachments."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter

from ..pages import output_path
from ..registry import register


@register(
    id="add_attachment",
    label="Add attachment",
    category="Attachments",
    summary="Embed a file inside the PDF as a named attachment.",
    inputs="many",
)
def add_attachment(sources: list[Path], out_dir: Path) -> list[Path]:
    if len(sources) != 2:
        raise ValueError("Add attachment takes exactly two files: the PDF and the file to embed.")
    pdf_src, attach_src = sources
    writer = PdfWriter()
    writer.append(str(pdf_src))
    writer.add_attachment(attach_src.name, attach_src.read_bytes())
    target = output_path(out_dir, f"{pdf_src.stem}-attached")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="extract_attachments",
    label="Extract attachments",
    category="Attachments",
    summary="Save every embedded file attachment to disk.",
    outputs="many",
)
def extract_attachments(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    if not reader.attachments:
        raise ValueError("This document has no attachments.")
    written = []
    for name, blobs in reader.attachments.items():
        stem = Path(name).stem or name
        suffix = Path(name).suffix or ""
        for i, blob in enumerate(blobs):
            target = output_path(out_dir, stem if i == 0 else f"{stem}-{i}", suffix)
            target.write_bytes(blob)
            written.append(target)
    return written
