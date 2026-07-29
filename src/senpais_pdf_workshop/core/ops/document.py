"""Operations that edit document-level structure: metadata, outline, forms."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject

from ..pages import output_path
from ..registry import Param, register


@register(
    id="edit_metadata",
    label="Edit metadata",
    category="Metadata",
    summary="Set the title, author, subject, and keywords stored in the document.",
    params=(
        Param("title", "str", "Title", default="", help="e.g. Quarterly Report"),
        Param("author", "str", "Author", default="", help="e.g. Jane Doe"),
        Param("subject", "str", "Subject", default="", help="e.g. Q3 financial summary"),
        Param(
            "keywords",
            "str",
            "Keywords",
            default="",
            help="Comma separated, e.g. finance, quarterly, draft",
        ),
    ),
)
def edit_metadata(
    sources: list[Path],
    out_dir: Path,
    title: str = "",
    author: str = "",
    subject: str = "",
    keywords: str = "",
) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    writer = PdfWriter()
    writer.append(reader)
    merged = dict(reader.metadata or {})
    values = {
        "/Title": title,
        "/Author": author,
        "/Subject": subject,
        "/Keywords": keywords,
    }
    merged.update({k: v for k, v in values.items() if v})
    writer.add_metadata(merged)
    target = output_path(out_dir, f"{src.stem}-metadata")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="edit_bookmarks",
    label="Edit bookmarks",
    category="Metadata",
    summary="Replace the document outline with the bookmarks you list.",
    params=(
        Param(
            "bookmarks",
            "str",
            "Bookmarks",
            required=True,
            help="Title:page pairs separated by semicolons, e.g. Chapter 1:1;Chapter 2:5",
        ),
    ),
)
def edit_bookmarks(sources: list[Path], out_dir: Path, bookmarks: str = "") -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    total = len(reader.pages)
    writer = PdfWriter()
    writer.append(reader, import_outline=False)
    for entry in bookmarks.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        title, _, page_s = entry.rpartition(":")
        page_s = page_s.strip()
        if not title or not page_s.isdigit():
            raise ValueError(f"Bad bookmark entry '{entry}', expected 'Title:page'.")
        page_num = int(page_s) - 1
        if page_num < 0 or page_num >= total:
            raise ValueError(f"Bookmark page {page_s} is outside this document (1-{total}).")
        writer.add_outline_item(title, page_num)
    target = output_path(out_dir, f"{src.stem}-bookmarked")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="flatten_forms",
    label="Flatten form fields",
    category="Forms",
    summary="Burn form field values into the page content and remove the interactive fields.",
)
def flatten_forms(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    writer = PdfWriter()
    writer.append(str(src))
    if "/AcroForm" not in writer.root_object:
        raise ValueError("This document has no form fields.")
    writer.update_page_form_field_values(None, {}, flatten=True)
    for page in writer.pages:
        if "/Annots" in page:
            kept = ArrayObject(
                a for a in page["/Annots"] if a.get_object().get("/Subtype") != "/Widget"
            )
            if kept:
                page[NameObject("/Annots")] = kept
            else:
                del page[NameObject("/Annots")]
    del writer.root_object[NameObject("/AcroForm")]
    target = output_path(out_dir, f"{src.stem}-flattened")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="fill_form",
    label="Fill form fields",
    category="Forms",
    summary="Set the values of an AcroForm's fields, optionally flattening them in.",
    params=(
        Param(
            "values",
            "str",
            "Field values",
            required=True,
            help="Field=Value pairs separated by semicolons, e.g. Name=Jane Doe;Date=2026-07-29",
        ),
        Param(
            "flatten",
            "bool",
            "Flatten after filling",
            default=False,
            help="Burns the values into the page and removes the interactive fields",
        ),
    ),
)
def fill_form(
    sources: list[Path], out_dir: Path, values: str = "", flatten: bool = False
) -> list[Path]:
    src = sources[0]
    writer = PdfWriter()
    writer.append(str(src))
    if "/AcroForm" not in writer.root_object:
        raise ValueError("This document has no form fields.")
    fields: dict[str, str] = {}
    for entry in values.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        name, sep, value = entry.partition("=")
        if not sep:
            raise ValueError(f"Bad field entry '{entry}', expected 'Field=Value'.")
        fields[name.strip()] = value.strip()
    if not fields:
        raise ValueError("No field values given.")
    writer.update_page_form_field_values(None, fields, flatten=flatten)
    if flatten:
        # pypdf's flatten=True only burns the appearance into the page content --
        # it doesn't remove the widget annotations or /AcroForm, so do that
        # ourselves to actually deliver on "removes editability".
        for page in writer.pages:
            if "/Annots" in page:
                kept = ArrayObject(
                    a for a in page["/Annots"] if a.get_object().get("/Subtype") != "/Widget"
                )
                if kept:
                    page[NameObject("/Annots")] = kept
                else:
                    del page[NameObject("/Annots")]
        del writer.root_object[NameObject("/AcroForm")]
    target = output_path(out_dir, f"{src.stem}-filled")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]
