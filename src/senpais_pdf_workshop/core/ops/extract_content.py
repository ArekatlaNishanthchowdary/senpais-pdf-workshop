"""Operations that pull content out of a PDF: images and text."""

from __future__ import annotations

import difflib
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


def _diff_report(name_a: str, name_b: str, pages_a: list[str], pages_b: list[str]) -> str:
    """Page-level diff: matches pages by content (so an inserted/deleted page
    doesn't shift every index after it out of alignment), then line-diffs
    whatever pages get paired up as changed."""
    matcher = difflib.SequenceMatcher(a=pages_a, b=pages_b, autojunk=False)
    same = added = removed = changed = 0
    body: list[str] = []

    def removed_block(indices: range) -> None:
        nonlocal removed
        for i in indices:
            removed += 1
            body.append(f"## Page {i + 1} removed (only in {name_a})\n")

    def added_block(indices: range) -> None:
        nonlocal added
        for j in indices:
            added += 1
            body.append(f"## Page {j + 1} added (only in {name_b})\n")

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            same += i2 - i1
        elif tag == "delete":
            removed_block(range(i1, i2))
        elif tag == "insert":
            added_block(range(j1, j2))
        elif tag == "replace":
            pair_count = min(i2 - i1, j2 - j1)
            for k in range(pair_count):
                ia, jb = i1 + k, j1 + k
                changed += 1
                body.append(f"## Page {ia + 1} -> {jb + 1} changed\n")
                diff_lines = list(
                    difflib.unified_diff(
                        pages_a[ia].splitlines(),
                        pages_b[jb].splitlines(),
                        lineterm="",
                    )
                )
                body.append("\n".join(diff_lines[2:]) or "(no visible text difference)")
                body.append("")
            removed_block(range(i1 + pair_count, i2))
            added_block(range(j1 + pair_count, j2))

    summary = f"{same} unchanged, {changed} changed, {added} added, {removed} removed"
    header = [f"# Comparing {name_a} vs {name_b}", "", summary, ""]
    if not body:
        body = ["No differences found."]
    return "\n".join(header + body)


@register(
    id="compare",
    label="Compare two PDFs",
    category="Extract",
    summary="Produce a page-by-page diff report between two PDFs as a Markdown file.",
    inputs="many",
)
def compare(sources: list[Path], out_dir: Path) -> list[Path]:
    if len(sources) != 2:
        raise ValueError("Compare takes exactly two files: the original and the revised PDF.")
    src_a, src_b = sources
    pages_a = [page.extract_text() or "" for page in PdfReader(str(src_a)).pages]
    pages_b = [page.extract_text() or "" for page in PdfReader(str(src_b)).pages]
    report = _diff_report(src_a.name, src_b.name, pages_a, pages_b)
    target = output_path(out_dir, f"{src_a.stem}-vs-{src_b.stem}", ".md")
    target.write_text(report, encoding="utf-8")
    return [target]
