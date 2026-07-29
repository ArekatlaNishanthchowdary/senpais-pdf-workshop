"""Tests for real redaction (core/ops/security.py:redact).

The point being tested isn't "does it run" -- it's that the redacted text is
actually gone from the underlying data (extract_text returns nothing on a
redacted page), not merely covered by a drawn box a viewer could lift text
out from underneath.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from senpais_pdf_workshop.core.ops._draw import draw_text
from senpais_pdf_workshop.core.registry import REGISTRY, load_operations

load_operations()


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    """Page 1 has a sensitive line and a fine line; page 2 has nothing sensitive."""
    writer = PdfWriter()
    page1 = writer.add_blank_page(width=400, height=200)
    draw_text(writer, page1, "Secret account number 12345", 20, 100, size=14)
    draw_text(writer, page1, "This part is fine to see.", 20, 60, size=14)
    page2 = writer.add_blank_page(width=400, height=200)
    draw_text(writer, page2, "Nothing sensitive on this page.", 20, 100, size=14)
    target = tmp_path / "sample.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


def test_redact_removes_text_from_matched_page(two_page_pdf, tmp_path):
    out = REGISTRY["redact"].run([two_page_pdf], tmp_path / "o", text="account number 12345")[0]
    reader = PdfReader(str(out))
    assert reader.pages[0].extract_text() == ""
    assert len(reader.pages[0].images) == 1  # the page is now a raster image


def test_redact_leaves_unmatched_pages_untouched(two_page_pdf, tmp_path):
    out = REGISTRY["redact"].run([two_page_pdf], tmp_path / "o", text="account number 12345")[0]
    reader = PdfReader(str(out))
    assert "Nothing sensitive on this page." in reader.pages[1].extract_text()
    assert not reader.pages[1].images


def test_redact_paints_over_the_matched_region(two_page_pdf, tmp_path):
    out = REGISTRY["redact"].run(
        [two_page_pdf], tmp_path / "o", text="account number 12345", dpi=200
    )[0]
    reader = PdfReader(str(out))
    image = reader.pages[0].images[0].image.convert("RGB")
    scale = 200 / 72
    assert image.getpixel((int(100 * scale), int(95 * scale))) == (0, 0, 0)
    assert image.getpixel((int(20 * scale), int(150 * scale))) == (255, 255, 255)


def test_redact_is_case_insensitive(two_page_pdf, tmp_path):
    out = REGISTRY["redact"].run([two_page_pdf], tmp_path / "o", text="SECRET ACCOUNT")[0]
    assert PdfReader(str(out)).pages[0].extract_text() == ""


def test_redact_rejects_no_match(two_page_pdf, tmp_path):
    with pytest.raises(ValueError, match="not found"):
        REGISTRY["redact"].run([two_page_pdf], tmp_path / "o", text="not anywhere in this file")


def test_redact_pages_param_restricts_the_scan(two_page_pdf, tmp_path):
    # the match is on page 1; restricting the scan to page 2 should miss it
    with pytest.raises(ValueError, match="not found"):
        REGISTRY["redact"].run(
            [two_page_pdf], tmp_path / "o", text="account number 12345", pages="2"
        )
