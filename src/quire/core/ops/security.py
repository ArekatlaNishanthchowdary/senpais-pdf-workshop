"""Password and metadata operations, built on pikepdf/QPDF."""

from __future__ import annotations

import secrets
from pathlib import Path

import pikepdf

from ..pages import output_path
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
