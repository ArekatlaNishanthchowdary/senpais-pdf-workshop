"""Password and metadata operations, built on pikepdf/QPDF."""

from __future__ import annotations

import secrets
from pathlib import Path

import pdfplumber
import pikepdf
import pypdfium2 as pdfium
from PIL import ImageDraw
from pypdf import PdfReader, PdfWriter

from ._draw import draw_image
from ._pdfminer_fix import reset_pdfminer_font_cache
from ..pages import output_path, parse_range
from ..registry import Param, register


@register(
    id="protect",
    label="Add a password",
    category="Security",
    summary="Encrypt the document so it cannot be opened without the password.",
    params=(
        Param("password", "password", "Password", required=True),
        Param(
            "allow_printing",
            "bool",
            "Allow printing",
            default=True,
            help="Uncheck to block printing for readers who open with the user password",
        ),
    ),
)
def protect(
    sources: list[Path],
    out_dir: Path,
    password: str = "",
    allow_printing: bool = True,
) -> list[Path]:
    src = sources[0]
    target = output_path(out_dir, f"{src.stem}-protected")
    permissions = pikepdf.Permissions(
        print_lowres=allow_printing,
        print_highres=allow_printing,
    )
    with pikepdf.open(str(src)) as pdf:
        pdf.save(
            str(target),
            encryption=pikepdf.Encryption(
                user=password, owner=password, allow=permissions
            ),
        )
    return [target]


@register(
    id="unlock",
    label="Remove a password",
    category="Security",
    summary="Save an unencrypted copy. You need the current password to do this.",
    params=(Param("password", "password", "Current password", required=True),),
)
def unlock(sources: list[Path], out_dir: Path, password: str = "") -> list[Path]:
    src = sources[0]
    target = output_path(out_dir, f"{src.stem}-unlocked")
    try:
        with pikepdf.open(str(src), password=password) as pdf:
            pdf.save(str(target))
    except pikepdf.PasswordError as exc:
        raise ValueError("That password did not open the document.") from exc
    return [target]


@register(
    id="scrub",
    label="Strip metadata",
    category="Security",
    summary="Remove author, title, producer, and XMP metadata from the document.",
)
def scrub(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    target = output_path(out_dir, f"{src.stem}-clean")
    with pikepdf.open(str(src)) as pdf:
        if "/Info" in pdf.trailer:
            del pdf.trailer["/Info"]
        if "/Metadata" in pdf.Root:
            del pdf.Root["/Metadata"]
        pdf.save(str(target))
    return [target]


@register(
    id="repair",
    label="Repair document",
    category="Security",
    summary="Rewrite the file structure to fix damaged or non-conforming PDFs.",
)
def repair(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    target = output_path(out_dir, f"{src.stem}-repaired")
    with pikepdf.open(str(src), allow_overwriting_input=False) as pdf:
        pdf.save(str(target), linearize=True)
    return [target]


@register(
    id="set_permissions",
    label="Set permissions",
    category="Security",
    summary="Restrict printing, copying, or editing without requiring a password to open.",
    params=(
        Param("allow_printing", "bool", "Allow printing", default=True),
        Param("allow_copying", "bool", "Allow copying text and images", default=True),
        Param("allow_annotation", "bool", "Allow annotations", default=True),
        Param("allow_modify", "bool", "Allow other modification", default=True),
    ),
)
def set_permissions(
    sources: list[Path],
    out_dir: Path,
    allow_printing: bool = True,
    allow_copying: bool = True,
    allow_annotation: bool = True,
    allow_modify: bool = True,
) -> list[Path]:
    src = sources[0]
    target = output_path(out_dir, f"{src.stem}-restricted")
    permissions = pikepdf.Permissions(
        print_lowres=allow_printing,
        print_highres=allow_printing,
        extract=allow_copying,
        modify_annotation=allow_annotation,
        modify_form=allow_modify,
        modify_other=allow_modify,
        modify_assembly=allow_modify,
    )
    # ponytail: random owner password never surfaced to the user -- the document
    # opens with no prompt, but only the (unknown) owner password could lift these
    # restrictions in a compliant reader.
    owner_password = secrets.token_urlsafe(16)
    with pikepdf.open(str(src)) as pdf:
        pdf.save(
            str(target),
            encryption=pikepdf.Encryption(user="", owner=owner_password, allow=permissions),
        )
    return [target]


@register(
    id="redact",
    label="Redact text",
    category="Security",
    summary="Permanently remove matching text from the page, not just draw over it.",
    params=(
        Param(
            "text",
            "str",
            "Text to redact",
            required=True,
            help="Case-insensitive, matched as plain text (not a pattern)",
        ),
        Param("pages", "page_range", "Pages to scan", default="all", help="Blank means all"),
        Param("dpi", "int", "Resolution (DPI)", default=200, minimum=100, maximum=400),
    ),
)
def redact(
    sources: list[Path], out_dir: Path, text: str = "", pages: str = "all", dpi: int = 200
) -> list[Path]:
    # ponytail: any page containing a match is rasterized WHOLE, not just the
    # matched region -- surgically deleting individual content-stream
    # operators would also need to catch hidden/clipped/invisible text and
    # other objects sharing that space, which a content-stream parser can
    # miss. Rasterizing the entire page guarantees nothing text-based
    # survives on it, at the cost of also flattening the rest of that page's
    # text (same trade-off `grayscale` already makes for colour). Pages with
    # no match keep their original, still-searchable content untouched.
    reset_pdfminer_font_cache()
    src = sources[0]
    with pdfplumber.open(str(src)) as plumber_pdf:
        total = len(plumber_pdf.pages)
        targets = set(parse_range(pages, total))
        matches_by_page: dict[int, list[tuple[float, float, float, float]]] = {}
        for index in targets:
            found = plumber_pdf.pages[index].search(text, regex=False, case=False)
            if found:
                matches_by_page[index] = [
                    (m["x0"], m["top"], m["x1"], m["bottom"]) for m in found
                ]

    if not matches_by_page:
        raise ValueError(f"'{text}' was not found on the selected pages.")

    reader = PdfReader(str(src))
    pdf = pdfium.PdfDocument(str(src))
    writer = PdfWriter()
    scale = dpi / 72
    for index, page in enumerate(reader.pages):
        if index not in matches_by_page:
            writer.add_page(page)
            continue
        width_pt, height_pt = float(page.mediabox.width), float(page.mediabox.height)
        image = pdf[index].render(scale=scale).to_pil().convert("RGB")
        draw = ImageDraw.Draw(image)
        for x0, top, x1, bottom in matches_by_page[index]:
            draw.rectangle([x0 * scale, top * scale, x1 * scale, bottom * scale], fill=(0, 0, 0))
        out_page = writer.add_blank_page(width=width_pt, height=height_pt)
        draw_image(writer, out_page, image, 0, 0, width_pt, height_pt)

    target = output_path(out_dir, f"{src.stem}-redacted")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]
