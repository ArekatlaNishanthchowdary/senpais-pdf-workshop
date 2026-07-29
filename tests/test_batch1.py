"""Tests for the batch-1 operations: no new runtime dependency beyond Pillow."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from quire.core.registry import REGISTRY, load_operations

load_operations()


def pages(path: Path) -> int:
    return len(PdfReader(str(path)).pages)


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    writer = PdfWriter()
    for _ in range(6):
        writer.add_blank_page(width=200, height=200)
    target = tmp_path / "sample.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


@pytest.fixture
def bookmarked(tmp_path: Path) -> Path:
    writer = PdfWriter()
    for _ in range(9):
        writer.add_blank_page(width=200, height=200)
    writer.add_outline_item("Intro", 0)
    writer.add_outline_item("Middle", 3)
    writer.add_outline_item("End", 6)
    target = tmp_path / "bookmarked.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


@pytest.fixture
def image_file(tmp_path: Path) -> Path:
    path = tmp_path / "stamp.png"
    Image.new("RGB", (40, 20), (10, 20, 30)).save(path)
    return path


@pytest.fixture
def form_pdf(tmp_path: Path) -> Path:
    """A minimal single-field AcroForm document, built by hand (pypdf can't author forms)."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)

    appearance = DecodedStreamObject()
    appearance.set_data(b"BT /Helv 10 Tf 2 2 Td (hi) Tj ET")
    appearance[NameObject("/Type")] = NameObject("/XObject")
    appearance[NameObject("/Subtype")] = NameObject("/Form")
    appearance[NameObject("/BBox")] = ArrayObject(
        [NumberObject(0), NumberObject(0), NumberObject(100), NumberObject(20)]
    )
    ap_ref = writer._add_object(appearance)

    field = DictionaryObject(
        {
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject("Field1"),
            NameObject("/V"): TextStringObject("hi"),
            NameObject("/Rect"): ArrayObject(
                [NumberObject(10), NumberObject(10), NumberObject(110), NumberObject(30)]
            ),
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/AP"): DictionaryObject({NameObject("/N"): ap_ref}),
        }
    )
    field_ref = writer._add_object(field)
    page[NameObject("/Annots")] = ArrayObject([field_ref])

    acro_form = DictionaryObject(
        {
            NameObject("/Fields"): ArrayObject([field_ref]),
            NameObject("/NeedAppearances"): BooleanObject(True),
        }
    )
    writer.root_object[NameObject("/AcroForm")] = acro_form

    target = tmp_path / "form.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


# -- organise --------------------------------------------------------------


def test_reorder(sample, tmp_path):
    out = REGISTRY["reorder"].run([sample], tmp_path / "o", order="3,1,2")[0]
    assert pages(out) == 3


def test_reorder_rejects_out_of_range(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["reorder"].run([sample], tmp_path / "o", order="99")


def test_insert(sample, tmp_path):
    out = REGISTRY["insert"].run([sample, sample], tmp_path / "o", position=2)[0]
    assert pages(out) == 12


def test_insert_at_end(sample, tmp_path):
    out = REGISTRY["insert"].run([sample, sample], tmp_path / "o", position=6)[0]
    assert pages(out) == 12


def test_split_by_count(sample, tmp_path):
    out = REGISTRY["split_by_count"].run([sample], tmp_path / "o", count=4)
    assert len(out) == 2
    assert pages(out[0]) == 4
    assert pages(out[1]) == 2


def test_split_by_bookmarks(bookmarked, tmp_path):
    out = REGISTRY["split_by_bookmarks"].run([bookmarked], tmp_path / "o")
    assert len(out) == 3
    assert pages(out[0]) == 3
    assert pages(out[1]) == 3
    assert pages(out[2]) == 3


# -- layout ------------------------------------------------------------------


def test_crop(sample, tmp_path):
    out = REGISTRY["crop"].run([sample], tmp_path / "o", left=10, right=10, top=10, bottom=10)[0]
    box = PdfReader(str(out)).pages[0].mediabox
    assert float(box.width) == 180
    assert float(box.height) == 180


def test_crop_rejects_too_much_margin(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["crop"].run([sample], tmp_path / "o", left=150, right=150)


def test_resize_preset(sample, tmp_path):
    out = REGISTRY["resize"].run([sample], tmp_path / "o", preset="A4")[0]
    box = PdfReader(str(out)).pages[0].mediabox
    assert round(float(box.width)) == 595
    assert round(float(box.height)) == 842


def test_resize_scale(sample, tmp_path):
    out = REGISTRY["resize"].run([sample], tmp_path / "o", preset="Custom", scale=2.0)[0]
    box = PdfReader(str(out)).pages[0].mediabox
    assert round(float(box.width)) == 400


def test_n_up(sample, tmp_path):
    out = REGISTRY["n_up"].run([sample], tmp_path / "o", per_sheet="2")[0]
    assert pages(out) == 3


def test_booklet(sample, tmp_path):
    out = REGISTRY["booklet"].run([sample], tmp_path / "o")[0]
    assert pages(out) == 4  # 6 pages padded to 8 -> 4 sheet-sides (2 physical sheets)


# -- annotate ------------------------------------------------------------------


def test_page_numbers(sample, tmp_path):
    out = REGISTRY["page_numbers"].run([sample], tmp_path / "o", format="Page {n} of {total}")[0]
    reader = PdfReader(str(out))
    assert "Page 1 of 6" in reader.pages[0].extract_text()
    assert "Page 6 of 6" in reader.pages[5].extract_text()


def test_watermark_text(sample, tmp_path):
    out = REGISTRY["watermark_text"].run([sample], tmp_path / "o", text="CONFIDENTIAL")[0]
    assert "CONFIDENTIAL" in PdfReader(str(out)).pages[0].extract_text()


def test_watermark_image(sample, image_file, tmp_path):
    out = REGISTRY["watermark_image"].run([sample, image_file], tmp_path / "o")[0]
    reader = PdfReader(str(out))
    assert len(reader.pages[0].images) == 1


def test_watermark_image_multiple_pdfs(sample, image_file, tmp_path):
    second = tmp_path / "second.pdf"
    second.write_bytes(sample.read_bytes())
    written = REGISTRY["watermark_image"].run([sample, second, image_file], tmp_path / "o")
    assert len(written) == 2
    assert {p.stem for p in written} == {"sample-stamped", "second-stamped"}
    for out in written:
        assert len(PdfReader(str(out)).pages[0].images) == 1


def test_overlay_over_and_under(sample, tmp_path):
    over_out = REGISTRY["overlay"].run([sample, sample], tmp_path / "o1", mode="over")[0]
    under_out = REGISTRY["overlay"].run([sample, sample], tmp_path / "o2", mode="under")[0]
    assert pages(over_out) == 6
    assert pages(under_out) == 6


# -- document / forms ---------------------------------------------------------


def test_edit_metadata(sample, tmp_path):
    out = REGISTRY["edit_metadata"].run([sample], tmp_path / "o", title="My Title", author="Me")[0]
    meta = PdfReader(str(out)).metadata
    assert meta.title == "My Title"
    assert meta.author == "Me"


def test_edit_metadata_leaves_blank_fields_untouched(sample, tmp_path):
    first = REGISTRY["edit_metadata"].run([sample], tmp_path / "o1", title="Keep Me")[0]
    second = REGISTRY["edit_metadata"].run([first], tmp_path / "o2", author="New Author")[0]
    meta = PdfReader(str(second)).metadata
    assert meta.title == "Keep Me"
    assert meta.author == "New Author"


def test_edit_bookmarks(sample, tmp_path):
    out = REGISTRY["edit_bookmarks"].run(
        [sample], tmp_path / "o", bookmarks="Start:1;Middle:4"
    )[0]
    reader = PdfReader(str(out))
    titles = [item.title for item in reader.outline]
    assert titles == ["Start", "Middle"]


def test_edit_bookmarks_rejects_bad_page(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["edit_bookmarks"].run([sample], tmp_path / "o", bookmarks="Bad:99")


def test_flatten_forms(form_pdf, tmp_path):
    out = REGISTRY["flatten_forms"].run([form_pdf], tmp_path / "o")[0]
    reader = PdfReader(str(out))
    assert "/AcroForm" not in reader.trailer["/Root"]
    assert "/Annots" not in reader.pages[0] or not reader.pages[0]["/Annots"]


def test_flatten_forms_rejects_document_without_forms(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["flatten_forms"].run([sample], tmp_path / "o")


def test_fill_form(form_pdf, tmp_path):
    out = REGISTRY["fill_form"].run([form_pdf], tmp_path / "o", values="Field1=filled in")[0]
    reader = PdfReader(str(out))
    assert reader.get_fields()["Field1"]["/V"] == "filled in"


def test_fill_form_can_flatten(form_pdf, tmp_path):
    out = REGISTRY["fill_form"].run(
        [form_pdf], tmp_path / "o", values="Field1=filled in", flatten=True
    )[0]
    reader = PdfReader(str(out))
    assert "/AcroForm" not in reader.trailer["/Root"]


def test_fill_form_rejects_bad_syntax(form_pdf, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["fill_form"].run([form_pdf], tmp_path / "o", values="not a pair")


# -- attachments / extraction ---------------------------------------------------


def test_add_and_extract_attachment(sample, tmp_path):
    note = tmp_path / "note.txt"
    note.write_text("hello world")
    attached = REGISTRY["add_attachment"].run([sample, note], tmp_path / "o")[0]
    out = REGISTRY["extract_attachments"].run([attached], tmp_path / "o2")
    assert len(out) == 1
    assert out[0].read_bytes() == b"hello world"


def test_extract_attachments_rejects_document_without_attachments(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["extract_attachments"].run([sample], tmp_path / "o")


def test_extract_images(sample, image_file, tmp_path):
    stamped = REGISTRY["watermark_image"].run([sample, image_file], tmp_path / "o")[0]
    out = REGISTRY["extract_images"].run([stamped], tmp_path / "o2")
    assert len(out) >= 1


def test_extract_images_rejects_document_without_images(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["extract_images"].run([sample], tmp_path / "o")


def test_extract_text(sample, tmp_path):
    out = REGISTRY["extract_text"].run([sample], tmp_path / "o")[0]
    assert out.suffix == ".txt"
    assert out.exists()


def test_pdf_to_xml(sample, tmp_path):
    out = REGISTRY["pdf_to_xml"].run([sample], tmp_path / "o")[0]
    text = out.read_text(encoding="utf-8")
    assert out.suffix == ".xml"
    assert text.count("<page number=") == 6


# -- security ------------------------------------------------------------------


def test_set_permissions(sample, tmp_path):
    out = REGISTRY["set_permissions"].run([sample], tmp_path / "o", allow_printing=False)[0]
    reader = PdfReader(str(out))
    assert reader.is_encrypted
    assert len(reader.pages) == 6  # opens with no password
