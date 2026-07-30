"""Tests for the pure file-promotion logic behind the preview-before-saving
flow: a run first lands in a scratch temp dir, and _move_written_files is
what promotes it into the user's real output folder on Save. No Qt/QApplication
needed -- same pattern as test_gui_thumbnails.py.
"""

from __future__ import annotations

from pathlib import Path

from senpais_pdf_workshop.gui.app import _move_written_files


def test_move_written_files_moves_and_cleans_up(tmp_path: Path):
    temp_dir = tmp_path / "scratch"
    temp_dir.mkdir()
    src = temp_dir / "result.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    out_dir = tmp_path / "out"

    moved = _move_written_files([src], out_dir, cleanup_dir=temp_dir)

    assert moved == [out_dir / "result.pdf"]
    assert moved[0].read_bytes() == b"%PDF-1.4 fake"
    assert not src.exists()
    assert not temp_dir.exists()


def test_move_written_files_overwrites_existing_target(tmp_path: Path):
    temp_dir = tmp_path / "scratch"
    temp_dir.mkdir()
    src = temp_dir / "result.pdf"
    src.write_bytes(b"new")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "result.pdf").write_bytes(b"stale")

    moved = _move_written_files([src], out_dir)

    assert moved[0].read_bytes() == b"new"
