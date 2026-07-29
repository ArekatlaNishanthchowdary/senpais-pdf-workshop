from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from senpais_pdf_workshop.core.pages import parse_range
from senpais_pdf_workshop.core.registry import REGISTRY, load_operations

load_operations()


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    writer = PdfWriter()
    for _ in range(6):
        writer.add_blank_page(width=200, height=200)
    target = tmp_path / "sample.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


def pages(path: Path) -> int:
    return len(PdfReader(str(path)).pages)


# -- page ranges ---------------------------------------------------------


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("1", [0]),
        ("1-3", [0, 1, 2]),
        ("1-2,5", [0, 1, 4]),
        ("4-", [3, 4, 5]),
        ("-2", [0, 1]),
        ("all", [0, 1, 2, 3, 4, 5]),
        ("3,1,3", [0, 2]),
    ],
)
def test_parse_range(spec, expected):
    assert parse_range(spec, 6) == expected


@pytest.mark.parametrize("spec", ["0", "7", "5-2", "99"])
def test_parse_range_rejects_bad_input(spec):
    with pytest.raises(ValueError):
        parse_range(spec, 6)


# -- operations ----------------------------------------------------------


def test_merge(sample, tmp_path):
    out = REGISTRY["merge"].run([sample, sample], tmp_path / "o")
    assert pages(out[0]) == 12


def test_split(sample, tmp_path):
    out = REGISTRY["split"].run([sample], tmp_path / "o")
    assert len(out) == 6
    assert all(pages(p) == 1 for p in out)


def test_extract(sample, tmp_path):
    out = REGISTRY["extract"].run([sample], tmp_path / "o", pages="1-2,5")
    assert pages(out[0]) == 3


def test_remove(sample, tmp_path):
    out = REGISTRY["remove"].run([sample], tmp_path / "o", pages="2,4")
    assert pages(out[0]) == 4


def test_remove_everything_is_refused(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["remove"].run([sample], tmp_path / "o", pages="all")


def test_rotate(sample, tmp_path):
    out = REGISTRY["rotate"].run([sample], tmp_path / "o", angle="90", pages="1")
    reader = PdfReader(str(out[0]))
    assert reader.pages[0].get("/Rotate") == 90
    assert reader.pages[1].get("/Rotate") in (0, None)


def test_reverse(sample, tmp_path):
    out = REGISTRY["reverse"].run([sample], tmp_path / "o")
    assert pages(out[0]) == 6


def test_password_round_trip(sample, tmp_path):
    locked = REGISTRY["protect"].run([sample], tmp_path / "o", password="hunter2")[0]
    assert PdfReader(str(locked)).is_encrypted
    opened = REGISTRY["unlock"].run([locked], tmp_path / "o", password="hunter2")[0]
    assert not PdfReader(str(opened)).is_encrypted


def test_unlock_with_wrong_password(sample, tmp_path):
    locked = REGISTRY["protect"].run([sample], tmp_path / "o", password="hunter2")[0]
    with pytest.raises(ValueError):
        REGISTRY["unlock"].run([locked], tmp_path / "o", password="nope")


def test_scrub(sample, tmp_path):
    out = REGISTRY["scrub"].run([sample], tmp_path / "o")
    assert not (PdfReader(str(out[0])).metadata or {})


def test_repair(sample, tmp_path):
    assert pages(REGISTRY["repair"].run([sample], tmp_path / "o")[0]) == 6


# -- registry contract ---------------------------------------------------


def test_single_input_ops_reject_multiple_files(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["split"].run([sample, sample], tmp_path / "o")


def test_required_params_are_enforced(sample, tmp_path):
    with pytest.raises(ValueError):
        REGISTRY["protect"].run([sample], tmp_path / "o", password="")


def test_every_operation_is_well_formed():
    assert REGISTRY
    for op in REGISTRY.values():
        assert op.summary.endswith("."), f"{op.id}: summary should be a sentence"
        assert op.label[0].isupper()
        for p in op.params:
            if p.kind == "choice":
                assert p.choices, f"{op.id}.{p.name}: choice needs options"
