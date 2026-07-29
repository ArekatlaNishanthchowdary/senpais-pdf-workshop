"""Page selection and output-naming helpers.

Page ranges are written the way people write them on paper: 1-based, inclusive,
comma separated, with an open end allowed. "1-3,7,10-" over a 12 page document
selects pages 1,2,3,7,10,11,12.
"""

from __future__ import annotations

from pathlib import Path


def parse_range(spec: str, total: int) -> list[int]:
    """Turn a range string into a sorted list of 0-based page indices."""
    if not spec or spec.strip().lower() in {"all", "*"}:
        return list(range(total))

    picked: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo_s, _, hi_s = chunk.partition("-")
            lo = int(lo_s) if lo_s.strip() else 1
            hi = int(hi_s) if hi_s.strip() else total
        else:
            lo = hi = int(chunk)
        if lo < 1 or hi > total or lo > hi:
            raise ValueError(
                f"Page range '{chunk}' is outside this document (1-{total})."
            )
        picked.update(range(lo - 1, hi))

    if not picked:
        raise ValueError("No pages selected.")
    return sorted(picked)


def output_path(out_dir: Path, stem: str, suffix: str = ".pdf") -> Path:
    """Return a free path in out_dir, adding -1, -2 ... if the name is taken."""
    candidate = out_dir / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = out_dir / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate
