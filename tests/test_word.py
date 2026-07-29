"""Tests for the pdfplumber/python-docx-backed PDF to Word operation (`extras`
group). Skips if either dependency isn't installed, same adaptive pattern as
test_convert.py / test_tables.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from pypdf import PdfWriter

from quire.core.ops._draw import draw_text
from quire.core.registry import REGISTRY, load_operations

load_operations()

HAS_WORD_DEPS = (
    importlib.util.find_spec("pdfplumber") is not None
    and importlib.util.find_spec("docx") is not None
)


@pytest.fixture
def titled_pdf(tmp_path: Path) -> Path:
    """One page: a large title line, two body lines, and a mid-size subheading."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    draw_text(writer, page, "My Document Title", 48, 780, size=20)
    draw_text(writer, page, "This is the first paragraph of body text.", 48, 750, size=11)
    draw_text(writer, page, "This is the second paragraph.", 48, 730, size=11)
    draw_text(writer, page, "A Subheading", 48, 700, size=15)
    target = tmp_path / "titled.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


@pytest.fixture
def blank_pdf(tmp_path: Path) -> Path:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    target = tmp_path / "blank.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


def test_pdf_to_word_reports_missing_extra(blank_pdf, tmp_path):
    if HAS_WORD_DEPS:
        pytest.skip("pdfplumber/python-docx installed; see test_pdf_to_word_detects_headings")
    with pytest.raises(ValueError, match="extras"):
        REGISTRY["pdf_to_word"].run([blank_pdf], tmp_path / "o")


def test_pdf_to_word_detects_headings(titled_pdf, tmp_path):
    if not HAS_WORD_DEPS:
        pytest.skip("pdfplumber/python-docx not installed")
    from docx import Document

    out = REGISTRY["pdf_to_word"].run([titled_pdf], tmp_path / "o")[0]
    assert out.suffix == ".docx"
    doc = Document(str(out))
    styles = [(p.style.name, p.text) for p in doc.paragraphs]
    assert styles[0] == ("Heading 1", "My Document Title")
    assert styles[1] == ("Normal", "This is the first paragraph of body text.")
    assert ("Heading 2", "A Subheading") in styles


def test_pdf_to_word_rejects_document_without_text(blank_pdf, tmp_path):
    if not HAS_WORD_DEPS:
        pytest.skip("pdfplumber/python-docx not installed")
    with pytest.raises(ValueError):
        REGISTRY["pdf_to_word"].run([blank_pdf], tmp_path / "o")
