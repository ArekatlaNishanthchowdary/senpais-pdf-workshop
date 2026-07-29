"""Tests for the pypdfium2/Pillow-backed image operations."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from quire.core.registry import REGISTRY, load_operations

load_operations()


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=200)
    target = tmp_path / "sample.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


@pytest.fixture
def colour_pdf(tmp_path: Path) -> Path:
    """A single page with a red rectangle, so grayscale conversion has something to check."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    stream = "1 0 0 rg 0 0 100 100 re f"
    from pypdf.generic import DecodedStreamObject, NameObject

    content = DecodedStreamObject()
    content.set_data(stream.encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(content)
    target = tmp_path / "colour.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


@pytest.fixture
def images(tmp_path: Path) -> list[Path]:
    paths = []
    for i, colour in enumerate([(255, 0, 0), (0, 255, 0)]):
        path = tmp_path / f"img{i}.png"
        Image.new("RGB", (30, 20), colour).save(path)
        paths.append(path)
    return paths


def test_pdf_to_image_png(sample, tmp_path):
    out = REGISTRY["pdf_to_image"].run([sample], tmp_path / "o", format="PNG", dpi=72)
    assert len(out) == 3
    assert all(p.suffix == ".png" for p in out)
    with Image.open(out[0]) as im:
        assert im.size == (200, 200)


def test_pdf_to_image_jpg(sample, tmp_path):
    out = REGISTRY["pdf_to_image"].run([sample], tmp_path / "o", format="JPG", dpi=72)
    assert all(p.suffix == ".jpg" for p in out)


def test_images_to_pdf(images, tmp_path):
    out = REGISTRY["images_to_pdf"].run(images, tmp_path / "o", name="combined")[0]
    reader = PdfReader(str(out))
    assert len(reader.pages) == 2


def test_grayscale(colour_pdf, tmp_path):
    out = REGISTRY["grayscale"].run([colour_pdf], tmp_path / "o", dpi=72)[0]
    reader = PdfReader(str(out))
    assert len(reader.pages) == 1
    image = reader.pages[0].images[0].image
    r, g, b = image.convert("RGB").getpixel((50, 50))
    assert r == g == b  # colour has been flattened to gray


def test_text_to_pdf(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("line one\nline two\n\nline four", encoding="utf-8")
    out = REGISTRY["text_to_pdf"].run([src], tmp_path / "o")[0]
    reader = PdfReader(str(out))
    text = reader.pages[0].extract_text()
    assert "line one" in text
    assert "line four" in text


def test_text_to_pdf_paginates_long_input(tmp_path):
    src = tmp_path / "big.txt"
    src.write_text("\n".join(f"line {i}" for i in range(200)), encoding="utf-8")
    out = REGISTRY["text_to_pdf"].run([src], tmp_path / "o")[0]
    reader = PdfReader(str(out))
    assert len(reader.pages) > 1


def test_pdf_to_web(sample, tmp_path):
    out = REGISTRY["pdf_to_web"].run([sample], tmp_path / "o", dpi=72)[0]
    html = out.read_text(encoding="utf-8")
    assert out.suffix == ".html"
    assert html.count("<img src='data:image/png;base64,") == 3
