"""Tests for the page-thumbnail rendering used by the GUI's drag-to-reorder
feature. Only the pure (non-Qt) rendering function is tested here -- it's the
part with real logic; the Qt drag-drop wiring around it has no logic of its
own to break.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from senpais_pdf_workshop.gui.app import render_thumbnail_frames


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=200, height=300)
    target = tmp_path / "sample.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


def test_render_thumbnail_frames_one_per_page(sample):
    frames = render_thumbnail_frames(sample)
    assert len(frames) == 4
    for data, width, height in frames:
        assert width * height * 3 == len(data)  # RGB888, 3 bytes/pixel
        assert max(width, height) == 90  # capped to the 90px thumbnail target


def test_render_thumbnail_frames_respects_max_pages(sample):
    frames = render_thumbnail_frames(sample, max_pages=2)
    assert len(frames) == 2
