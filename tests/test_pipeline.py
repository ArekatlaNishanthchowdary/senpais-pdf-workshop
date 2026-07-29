"""Tests for the pipeline engine (core/pipeline.py) and its CLI wiring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from senpais_pdf_workshop.cli import main as cli_main
from senpais_pdf_workshop.core.pipeline import Step, run_pipeline
from senpais_pdf_workshop.core.registry import load_operations

load_operations()


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=200, height=200)
    target = tmp_path / "sample.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


def test_run_pipeline_chains_steps(sample, tmp_path):
    steps = [
        Step("rotate", {"angle": "90", "pages": "all"}),
        Step("watermark_text", {"text": "DRAFT"}),
    ]
    out = run_pipeline(steps, [sample], tmp_path / "o")
    assert len(out) == 1
    reader = PdfReader(str(out[0]))
    assert reader.pages[0].get("/Rotate") == 90
    assert "DRAFT" in reader.pages[0].extract_text()


def test_run_pipeline_rejects_unknown_op(sample, tmp_path):
    with pytest.raises(ValueError, match="Unknown operation"):
        run_pipeline([Step("not_a_real_op")], [sample], tmp_path / "o")


def test_run_pipeline_rejects_empty_steps(sample, tmp_path):
    with pytest.raises(ValueError):
        run_pipeline([], [sample], tmp_path / "o")


def test_run_pipeline_propagates_arity_errors(sample, tmp_path):
    # split fans one file out to many; rotate then can't accept them all at once
    with pytest.raises(ValueError, match="exactly one"):
        run_pipeline([Step("split"), Step("rotate", {"angle": "90"})], [sample], tmp_path / "o")


def test_cli_pipeline_subcommand(sample, tmp_path, capsys):
    steps_file = tmp_path / "steps.json"
    steps_file.write_text(
        json.dumps([{"op": "rotate", "params": {"angle": "180", "pages": "all"}}]),
        encoding="utf-8",
    )
    out_dir = tmp_path / "o"
    exit_code = cli_main(["pipeline", str(steps_file), str(sample), "-o", str(out_dir)])
    assert exit_code == 0
    written = Path(capsys.readouterr().out.strip())
    assert PdfReader(str(written)).pages[0].get("/Rotate") == 180
