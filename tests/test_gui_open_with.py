"""Tests for the CLI-argument handling behind Windows' "Open with" support.

Only the pure argument-parsing function is tested here (no Qt/QApplication
needed) -- the same pattern used for the thumbnail renderer in
test_gui_thumbnails.py.
"""

from __future__ import annotations

from pathlib import Path

from senpais_pdf_workshop.gui.app import pdf_from_args


def test_pdf_from_args_finds_an_existing_pdf(tmp_path: Path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert pdf_from_args([str(pdf)]) == pdf


def test_pdf_from_args_ignores_a_missing_path(tmp_path: Path):
    assert pdf_from_args([str(tmp_path / "missing.pdf")]) is None


def test_pdf_from_args_ignores_non_pdf_files(tmp_path: Path):
    txt = tmp_path / "notes.txt"
    txt.write_text("hi", encoding="utf-8")
    assert pdf_from_args([str(txt)]) is None


def test_pdf_from_args_with_no_args():
    assert pdf_from_args([]) is None


def test_pdf_from_args_finds_pdf_among_other_arguments(tmp_path: Path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert pdf_from_args(["--some-flag", str(pdf)]) == pdf
