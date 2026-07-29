"""Operations that rearrange pages without touching their content."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter

from ..pages import output_path, parse_range
from ..registry import Param, register


@register(
    id="merge",
    label="Merge PDFs",
    category="Organise",
    summary="Join several PDFs into one, in the order given.",
    inputs="many",
    params=(
        Param("name", "str", "Output name", default="merged", help="Without .pdf"),
    ),
)
def merge(sources: list[Path], out_dir: Path, name: str = "merged") -> list[Path]:
    writer = PdfWriter()
    for src in sources:
        writer.append(str(src))
    target = output_path(out_dir, name or "merged")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="split",
    label="Split into single pages",
    category="Organise",
    summary="Write every page of the document to its own file.",
    outputs="many",
)
def split(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    written: list[Path] = []
    width = len(str(len(reader.pages)))
    for index, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        target = output_path(out_dir, f"{src.stem}-{index:0{width}d}")
        with target.open("wb") as fh:
            writer.write(fh)
        written.append(target)
    return written


@register(
    id="extract",
    label="Extract pages",
    category="Organise",
    summary="Keep only the pages you select and discard the rest.",
    params=(
        Param(
            "pages",
            "page_range",
            "Pages to keep",
            default="1",
            required=True,
            help="For example 1-3,7,10-",
        ),
    ),
)
def extract(sources: list[Path], out_dir: Path, pages: str = "1") -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for index in parse_range(pages, len(reader.pages)):
        writer.add_page(reader.pages[index])
    target = output_path(out_dir, f"{src.stem}-extracted")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="remove",
    label="Remove pages",
    category="Organise",
    summary="Delete the pages you select and keep everything else.",
    params=(
        Param(
            "pages",
            "page_range",
            "Pages to remove",
            default="1",
            required=True,
            help="For example 2,5-6",
        ),
    ),
)
def remove(sources: list[Path], out_dir: Path, pages: str = "1") -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    drop = set(parse_range(pages, len(reader.pages)))
    keep = [i for i in range(len(reader.pages)) if i not in drop]
    if not keep:
        raise ValueError("That would remove every page.")
    writer = PdfWriter()
    for index in keep:
        writer.add_page(reader.pages[index])
    target = output_path(out_dir, f"{src.stem}-trimmed")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="rotate",
    label="Rotate pages",
    category="Organise",
    summary="Turn selected pages clockwise by a multiple of 90 degrees.",
    params=(
        Param(
            "angle",
            "choice",
            "Rotation",
            default="90",
            choices=("90", "180", "270"),
            required=True,
        ),
        Param("pages", "page_range", "Pages", default="all", help="Blank means all"),
    ),
)
def rotate(
    sources: list[Path], out_dir: Path, angle: str = "90", pages: str = "all"
) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    targets = set(parse_range(pages, len(reader.pages)))
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index in targets:
            page.rotate(int(angle))
        writer.add_page(page)
    target = output_path(out_dir, f"{src.stem}-rotated")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="reverse",
    label="Reverse page order",
    category="Organise",
    summary="Put the last page first and the first page last.",
)
def reverse(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reversed(reader.pages):
        writer.add_page(page)
    target = output_path(out_dir, f"{src.stem}-reversed")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="reorder",
    label="Reorder pages",
    category="Organise",
    summary="Rearrange pages into the exact sequence you specify.",
    params=(
        Param(
            "order",
            "str",
            "New page order",
            required=True,
            help="Comma-separated 1-based page numbers, e.g. 3,1,2,4",
        ),
    ),
)
def reorder(sources: list[Path], out_dir: Path, order: str = "") -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    total = len(reader.pages)
    try:
        indices = [int(tok.strip()) - 1 for tok in order.split(",") if tok.strip()]
    except ValueError as exc:
        raise ValueError("Page order must be a comma-separated list of numbers.") from exc
    if not indices:
        raise ValueError("No pages given.")
    for i in indices:
        if i < 0 or i >= total:
            raise ValueError(f"Page {i + 1} is outside this document (1-{total}).")
    writer = PdfWriter()
    for i in indices:
        writer.add_page(reader.pages[i])
    target = output_path(out_dir, f"{src.stem}-reordered")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="insert",
    label="Insert PDF at a position",
    category="Organise",
    summary="Insert every page of one PDF into another at a given position.",
    inputs="many",
    params=(
        Param(
            "position",
            "int",
            "Insert after page",
            default=0,
            minimum=0,
            help="0 inserts before the first page",
        ),
    ),
)
def insert(sources: list[Path], out_dir: Path, position: int = 0) -> list[Path]:
    if len(sources) != 2:
        raise ValueError("Insert takes exactly two files: the base PDF and the PDF to insert.")
    base_src, insert_src = sources
    base = PdfReader(str(base_src))
    to_insert = PdfReader(str(insert_src))
    total = len(base.pages)
    if position < 0 or position > total:
        raise ValueError(f"Position must be between 0 and {total}.")
    writer = PdfWriter()
    for index, page in enumerate(base.pages):
        if index == position:
            for ipage in to_insert.pages:
                writer.add_page(ipage)
        writer.add_page(page)
    if position == total:
        for ipage in to_insert.pages:
            writer.add_page(ipage)
    target = output_path(out_dir, f"{base_src.stem}-inserted")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="split_by_count",
    label="Split by page count",
    category="Organise",
    summary="Break the document into chunks of a fixed number of pages.",
    outputs="many",
    params=(Param("count", "int", "Pages per chunk", default=1, minimum=1, required=True),),
)
def split_by_count(sources: list[Path], out_dir: Path, count: int = 1) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    total = len(reader.pages)
    chunks = -(-total // count)
    width = len(str(chunks))
    written: list[Path] = []
    for chunk_index, start in enumerate(range(0, total, count), start=1):
        writer = PdfWriter()
        for page in reader.pages[start : start + count]:
            writer.add_page(page)
        target = output_path(out_dir, f"{src.stem}-part-{chunk_index:0{width}d}")
        with target.open("wb") as fh:
            writer.write(fh)
        written.append(target)
    return written


@register(
    id="split_by_bookmarks",
    label="Split by bookmarks",
    category="Organise",
    summary="Break the document into one file per top-level bookmark.",
    outputs="many",
)
def split_by_bookmarks(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    total = len(reader.pages)
    pairs = sorted(
        {
            (reader.get_destination_page_number(item), item.title)
            for item in reader.outline
            if not isinstance(item, list)
        }
    )
    if not pairs:
        raise ValueError("This document has no top-level bookmarks.")
    written: list[Path] = []
    for i, (start, title) in enumerate(pairs):
        end = pairs[i + 1][0] if i + 1 < len(pairs) else total
        writer = PdfWriter()
        for page in reader.pages[start:end]:
            writer.add_page(page)
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()
        target = output_path(out_dir, f"{src.stem}-{safe or f'part-{i + 1}'}")
        with target.open("wb") as fh:
            writer.write(fh)
        written.append(target)
    return written
