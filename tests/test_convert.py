"""Tests for the external-binary operations.

Each test adapts to whatever toolchain this machine actually has: if the
binary is present, the real conversion runs end to end; if not, the test
verifies the operation detects the missing binary and raises a clear
ValueError instead of crashing. Tesseract happens to be present here, but is
too old for ocrmypdf, which exercises the "toolchain present but broken"
failure path instead of either of the other two.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from senpais_pdf_workshop.core.registry import REGISTRY, load_operations

load_operations()

HAS_GS = shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")
HAS_OFFICE = shutil.which("soffice") or shutil.which("libreoffice")

# ponytail: minimal hand-built OOXML, just enough for LibreOffice to open it --
# avoids adding python-docx as a dependency for one test fixture.
_DOCX_CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
_DOCX_RELS = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
_DOCX_DOCUMENT = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:p><w:r><w:t>Hello Quire test</w:t></w:r></w:p></w:body>
</w:document>"""


def _write_docx(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        zf.writestr("_rels/.rels", _DOCX_RELS)
        zf.writestr("word/document.xml", _DOCX_DOCUMENT)
    return path


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    target = tmp_path / "sample.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


def test_compress_reports_missing_ghostscript(sample, tmp_path):
    if HAS_GS:
        out = REGISTRY["compress"].run([sample], tmp_path / "o")[0]
        assert out.exists()
    else:
        with pytest.raises(ValueError, match="Ghostscript"):
            REGISTRY["compress"].run([sample], tmp_path / "o")


def test_pdf_to_pdfa_reports_missing_ghostscript(sample, tmp_path):
    if HAS_GS:
        out = REGISTRY["pdf_to_pdfa"].run([sample], tmp_path / "o")[0]
        assert out.exists()
    else:
        with pytest.raises(ValueError, match="Ghostscript"):
            REGISTRY["pdf_to_pdfa"].run([sample], tmp_path / "o")


def test_office_to_pdf_reports_missing_libreoffice(tmp_path):
    if HAS_OFFICE:
        doc = _write_docx(tmp_path / "doc.docx")
        out = REGISTRY["office_to_pdf"].run([doc], tmp_path / "o")[0]
        assert out.exists()
        assert PdfReader(str(out)).pages
    else:
        doc = tmp_path / "doc.docx"
        doc.write_bytes(b"not a real docx, just checking the missing-binary path")
        with pytest.raises(ValueError, match="LibreOffice"):
            REGISTRY["office_to_pdf"].run([doc], tmp_path / "o")


def test_office_to_pdf_batch_mixed_types(tmp_path):
    if not HAS_OFFICE:
        pytest.skip("LibreOffice not installed")
    # two files that share a stem (from different source folders) to exercise
    # the collision-safe naming, alongside a differently-named one
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    doc_a = _write_docx(tmp_path / "a" / "report.docx")
    doc_b = _write_docx(tmp_path / "b" / "report.docx")
    doc_c = _write_docx(tmp_path / "slides.docx")
    out = REGISTRY["office_to_pdf"].run([doc_a, doc_b, doc_c], tmp_path / "o")
    assert len(out) == 3
    assert len(set(out)) == 3  # distinct paths, not one overwriting another
    for path in out:
        assert path.exists()
        assert PdfReader(str(path)).pages


def test_ocr_fails_cleanly_or_succeeds(sample, tmp_path):
    """Whatever OCR toolchain this machine has (none, too old, or working), the
    operation must either produce a file or raise ValueError -- never let an
    internal ocrmypdf/tesseract exception escape unwrapped."""
    try:
        out = REGISTRY["ocr"].run([sample], tmp_path / "o")[0]
        assert out.exists()
    except ValueError:
        pass
