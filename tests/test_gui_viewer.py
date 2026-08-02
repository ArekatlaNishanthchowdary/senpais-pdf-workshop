"""Tests for the PDF viewer's text-selection and link hit-testing: the
pdfium-backed coordinate math (screen point -> PDF page point -> char index /
link rect) that makes text selectable and links clickable on top of the
rasterized page bitmap. Uses a real synthetic PDF (reportlab) and a headless
QApplication so the coordinates are checked against real pdfium data, not
mocks.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from reportlab.pdfgen import canvas

from senpais_pdf_workshop.gui.app import PdfViewerWindow, _page_links


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(path), pagesize=(300, 300))
    c.drawString(20, 250, "Hello selectable world")
    c.linkURL("https://example.com", (200, 240, 280, 260), relative=0)
    c.save()
    return path


def test_page_links_finds_uri_annotation(sample_pdf: Path):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(sample_pdf))
    assert _page_links(pdf[0]) == [((200.0, 240.0, 280.0, 260.0), "https://example.com")]


def _label_pos(height_pt: float, zoom: float, x_pt: float, y_pt: float) -> QPointF:
    # Inverse of PdfViewerWindow._point_to_pdf, at the given zoom.
    return QPointF(x_pt * zoom, (height_pt - y_pt) * zoom)


def test_drag_selection_resolves_to_typed_text(qapp, sample_pdf: Path, monkeypatch):
    viewer = PdfViewerWindow(sample_pdf)
    try:
        viewer._zoom = 1.0
        height_pt = viewer._page_sizes[0][1]

        viewer.begin_selection(0, _label_pos(height_pt, 1.0, 22, 254))
        viewer.extend_selection(0, _label_pos(height_pt, 1.0, 45, 254))
        selected = viewer.finish_selection(0, _label_pos(height_pt, 1.0, 45, 254))

        assert selected
        page_index, start, end = viewer._selection
        assert page_index == 0
        assert viewer._textpage(0).get_text_range(start, end - start) == "Hello"

        copied = {}
        monkeypatch.setattr(QApplication, "clipboard", staticmethod(lambda: _FakeClipboard(copied)))
        viewer._copy_selection()
        assert copied["text"] == "Hello"
    finally:
        viewer.close()


def test_plain_click_does_not_leave_a_selection(qapp, sample_pdf: Path):
    viewer = PdfViewerWindow(sample_pdf)
    try:
        viewer._zoom = 1.0
        height_pt = viewer._page_sizes[0][1]
        pos = _label_pos(height_pt, 1.0, 22, 254)

        viewer.begin_selection(0, pos)
        selected = viewer.finish_selection(0, pos)

        assert not selected
        assert viewer._selection is None
    finally:
        viewer.close()


def test_open_link_at_opens_the_uri(qapp, sample_pdf: Path, monkeypatch):
    viewer = PdfViewerWindow(sample_pdf)
    try:
        viewer._zoom = 1.0
        height_pt = viewer._page_sizes[0][1]
        opened = {}
        monkeypatch.setattr(
            "senpais_pdf_workshop.gui.app.QDesktopServices.openUrl",
            lambda url: opened.setdefault("url", url.toString()),
        )
        viewer.open_link_at(0, _label_pos(height_pt, 1.0, 240, 250))
        assert opened["url"] == "https://example.com"
    finally:
        viewer.close()


class _FakeClipboard:
    def __init__(self, store: dict) -> None:
        self._store = store

    def setText(self, text: str) -> None:
        self._store["text"] = text
