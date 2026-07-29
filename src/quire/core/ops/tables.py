"""PDF to Excel via real table detection (camelot-py), not a lossy PDF-import
round-trip. Kept out of the default install like OCR -- see the `extras` group
in pyproject.toml -- since its dependency chain (pandas, numpy, OpenCV) is
heavy for what is otherwise a lightweight, dependency-light project.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from ..pages import output_path
from ..registry import Param, register


@register(
    id="pdf_to_excel",
    label="PDF to Excel",
    category="Convert",
    summary="Detect ruled tables in a PDF and write them to a real, editable spreadsheet.",
    params=(
        Param(
            "pages",
            "str",
            "Pages to scan",
            default="all",
            help="camelot's own page syntax, e.g. 1,2,3 or 2-end or all",
        ),
    ),
)
def pdf_to_excel(sources: list[Path], out_dir: Path, pages: str = "all") -> list[Path]:
    try:
        import camelot
        import openpyxl
    except ImportError as exc:
        raise ValueError(
            'PDF to Excel needs the extras install: pip install "quire[extras]".'
        ) from exc

    src = sources[0]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tables = camelot.read_pdf(str(src), pages=pages or "all")
    except Exception as exc:
        raise ValueError(f"Table detection failed: {exc}") from exc
    if not tables:
        raise ValueError("No tables were detected in this document.")

    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for index, table in enumerate(tables, start=1):
        sheet = workbook.create_sheet(f"Table {index}")
        for row in table.df.itertuples(index=False):
            sheet.append(list(row))
    target = output_path(out_dir, f"{src.stem}-tables", ".xlsx")
    workbook.save(target)
    return [target]
