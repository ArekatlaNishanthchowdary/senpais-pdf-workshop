"""Operations that change the geometry of pages: size, cropping, imposition."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation

from ..pages import output_path
from ..registry import Param, register

_PAGE_SIZES = {"A4": (595.0, 842.0), "Letter": (612.0, 792.0), "Legal": (612.0, 1008.0)}
_GRIDS = {2: (1, 2), 4: (2, 2), 6: (2, 3), 9: (3, 3)}


@register(
    id="crop",
    label="Crop pages",
    category="Layout",
    summary="Trim a fixed margin off every side of every page, in points.",
    params=(
        Param("left", "float", "Left margin", default=0.0, minimum=0),
        Param("right", "float", "Right margin", default=0.0, minimum=0),
        Param("top", "float", "Top margin", default=0.0, minimum=0),
        Param("bottom", "float", "Bottom margin", default=0.0, minimum=0),
    ),
)
def crop(
    sources: list[Path],
    out_dir: Path,
    left: float = 0.0,
    right: float = 0.0,
    top: float = 0.0,
    bottom: float = 0.0,
) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        box = page.mediabox
        if left + right >= float(box.width) or top + bottom >= float(box.height):
            raise ValueError("Crop margins leave nothing on the page.")
        box.lower_left = (float(box.left) + left, float(box.bottom) + bottom)
        box.upper_right = (float(box.right) - right, float(box.top) - top)
        writer.add_page(page)
    target = output_path(out_dir, f"{src.stem}-cropped")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="resize",
    label="Resize pages",
    category="Layout",
    summary="Scale every page to a standard size or by a percentage.",
    params=(
        Param(
            "preset",
            "choice",
            "Target size",
            default="Custom",
            choices=("Custom", "A4", "Letter", "Legal"),
            required=True,
        ),
        Param(
            "scale",
            "float",
            "Scale factor",
            default=1.0,
            minimum=0.01,
            maximum=10.0,
            help="Used when target size is Custom, e.g. 0.5 for half size",
        ),
    ),
)
def resize(
    sources: list[Path], out_dir: Path, preset: str = "Custom", scale: float = 1.0
) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        if preset in _PAGE_SIZES:
            width, height = _PAGE_SIZES[preset]
            page.scale_to(width, height)
        else:
            page.scale_by(scale)
        writer.add_page(page)
    target = output_path(out_dir, f"{src.stem}-resized")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="n_up",
    label="N-up (multiple pages per sheet)",
    category="Layout",
    summary="Lay out several source pages onto each output sheet.",
    params=(
        Param(
            "per_sheet",
            "choice",
            "Pages per sheet",
            default="4",
            choices=("2", "4", "6", "9"),
            required=True,
        ),
    ),
)
def n_up(sources: list[Path], out_dir: Path, per_sheet: str = "4") -> list[Path]:
    src = sources[0]
    n = int(per_sheet)
    rows, cols = _GRIDS[n]
    reader = PdfReader(str(src))
    pages = list(reader.pages)
    if not pages:
        raise ValueError("This document has no pages.")
    sheet_w, sheet_h = float(pages[0].mediabox.width), float(pages[0].mediabox.height)
    cell_w, cell_h = sheet_w / cols, sheet_h / rows
    writer = PdfWriter()
    for start in range(0, len(pages), n):
        sheet = writer.add_blank_page(width=sheet_w, height=sheet_h)
        for slot, page in enumerate(pages[start : start + n]):
            row, col = divmod(slot, cols)
            src_w, src_h = float(page.mediabox.width), float(page.mediabox.height)
            fit = min(cell_w / src_w, cell_h / src_h)
            tx = col * cell_w + (cell_w - src_w * fit) / 2
            ty = sheet_h - (row + 1) * cell_h + (cell_h - src_h * fit) / 2
            sheet.merge_transformed_page(page, Transformation().scale(fit, fit).translate(tx, ty))
    target = output_path(out_dir, f"{src.stem}-{n}up")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]


@register(
    id="booklet",
    label="Arrange as booklet",
    category="Layout",
    summary="Reorder and lay out pages two-up for folded, saddle-stitched printing.",
)
def booklet(sources: list[Path], out_dir: Path) -> list[Path]:
    src = sources[0]
    reader = PdfReader(str(src))
    pages: list = list(reader.pages)
    if not pages:
        raise ValueError("This document has no pages.")
    page_w, page_h = float(pages[0].mediabox.width), float(pages[0].mediabox.height)
    padded = -(-len(pages) // 4) * 4
    pages += [None] * (padded - len(pages))

    # ponytail: single-signature imposition (whole document folded as one stack).
    # Fine for short booklets; long documents want multi-signature imposition instead.
    order: list[int | None] = []
    for i in range(padded // 4):
        order += [padded - 2 * i - 1, 2 * i, 2 * i + 1, padded - 2 * i - 2]

    writer = PdfWriter()
    for left_idx, right_idx in zip(order[0::2], order[1::2]):
        sheet = writer.add_blank_page(width=page_w * 2, height=page_h)
        for slot, idx in enumerate((left_idx, right_idx)):
            if idx is None or pages[idx] is None:
                continue
            sheet.merge_transformed_page(pages[idx], Transformation().translate(slot * page_w, 0))
    target = output_path(out_dir, f"{src.stem}-booklet")
    with target.open("wb") as fh:
        writer.write(fh)
    return [target]
