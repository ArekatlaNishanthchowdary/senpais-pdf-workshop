"""Operations that shell out to optional external tools: Ghostscript, LibreOffice,
OCRmyPDF/Tesseract. None of these are installed by `pip install senpais-pdf-workshop` -- they're
separate programs the user installs, and each operation checks for its binary
and raises a clear, actionable error instead of failing to import.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ..pages import output_path
from ..registry import Param, register
from ._binaries import require

_GS_NAMES = ("gs", "gswin64c", "gswin32c")
_OFFICE_NAMES = ("soffice", "libreoffice")
_GS_HINT = "Install Ghostscript (ghostscript.com) and make sure it is on PATH."
_QUALITY = {"screen": "/screen", "ebook": "/ebook", "printer": "/printer", "prepress": "/prepress"}


def _run_gs(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(
            f"Ghostscript failed: {result.stderr.strip() or result.stdout.strip()}"
        )


@register(
    id="compress",
    label="Compress",
    category="Convert",
    summary="Shrink file size by re-encoding images and fonts with Ghostscript.",
    params=(
        Param(
            "quality",
            "choice",
            "Quality preset",
            default="ebook",
            choices=("screen", "ebook", "printer", "prepress"),
            required=True,
        ),
    ),
)
def compress(sources: list[Path], out_dir: Path, quality: str = "ebook") -> list[Path]:
    gs = require(*_GS_NAMES, feature="Compress", install_hint=_GS_HINT)
    src = sources[0]
    target = output_path(out_dir, f"{src.stem}-compressed")
    _run_gs(
        [
            gs,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.5",
            f"-dPDFSETTINGS={_QUALITY[quality]}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={target}",
            str(src),
        ]
    )
    return [target]


@register(
    id="pdf_to_pdfa",
    label="PDF/A conversion",
    category="Convert",
    summary="Convert to the archival PDF/A format using Ghostscript.",
)
def pdf_to_pdfa(sources: list[Path], out_dir: Path) -> list[Path]:
    gs = require(*_GS_NAMES, feature="PDF/A conversion", install_hint=_GS_HINT)
    src = sources[0]
    target = output_path(out_dir, f"{src.stem}-pdfa")
    _run_gs(
        [
            gs,
            "-dPDFA=2",
            "-dBATCH",
            "-dNOPAUSE",
            "-dQUIET",
            "-dNOOUTERSAVE",
            "-sColorConversionStrategy=RGB",
            "-sDEVICE=pdfwrite",
            "-dPDFACompatibilityPolicy=1",
            f"-sOutputFile={target}",
            str(src),
        ]
    )
    return [target]


@register(
    id="office_to_pdf",
    label="Office documents to PDF",
    category="Convert",
    summary="Convert one or more Word, Excel, PowerPoint, or RTF files to PDF using LibreOffice.",
    inputs="many",
    outputs="many",
    input_formats=(
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf",
    ),
)
def office_to_pdf(sources: list[Path], out_dir: Path) -> list[Path]:
    soffice = require(
        *_OFFICE_NAMES,
        feature="Office conversion",
        install_hint="Install LibreOffice and make sure soffice is on PATH.",
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for src in sources:
        # ponytail: converted one at a time into its own temp dir, then moved
        # through output_path -- LibreOffice always names its output
        # `<stem>.pdf`, which would silently collide/overwrite when a batch
        # mixes files that share a stem (e.g. budget.docx + budget.xlsx).
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)],
                capture_output=True,
                text=True,
            )
            produced = Path(tmp) / f"{src.stem}.pdf"
            if result.returncode != 0 or not produced.exists():
                raise ValueError(
                    f"LibreOffice failed on {src.name}: "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
            target = output_path(out_dir, src.stem)
            target.write_bytes(produced.read_bytes())
            written.append(target)
    return written


@register(
    id="ocr",
    label="OCR (make searchable)",
    category="Convert",
    summary="Add a searchable text layer to a scanned PDF using OCRmyPDF and Tesseract.",
    params=(
        Param(
            "language",
            "str",
            "Language code(s)",
            default="eng",
            help="Tesseract language codes, comma separated, e.g. eng,fra",
        ),
        Param("force", "bool", "Reprocess pages that already have text", default=False),
    ),
)
def ocr(sources: list[Path], out_dir: Path, language: str = "eng", force: bool = False) -> list[Path]:
    try:
        import ocrmypdf
    except ImportError as exc:
        raise ValueError(
            'OCR needs the extras install: pip install "senpais-pdf-workshop[extras]", '
            "plus Tesseract installed and on PATH."
        ) from exc
    src = sources[0]
    target = output_path(out_dir, f"{src.stem}-ocr")
    languages = [tok.strip() for tok in language.split(",") if tok.strip()] or ["eng"]
    try:
        ocrmypdf.ocr(
            str(src), str(target), language=languages, force_ocr=force, progress_bar=False
        )
    except Exception as exc:
        raise ValueError(f"OCR failed: {exc}") from exc
    return [target]
