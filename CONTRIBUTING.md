# Contributing

Thanks for looking at this. The whole point of the registry architecture is
that adding a tool should be small — this doc is mostly about keeping it that
way.

## Setup

```bash
git clone https://github.com/ArekatlaNishanthchowdary/senpais-pdf-workshop.git
cd senpais-pdf-workshop
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,extras]"
pytest
```

`extras` pulls in the heavier optional dependencies (camelot-py, pdfplumber,
python-docx, python-pptx, ocrmypdf) so the full test suite can exercise every
operation. Without it, tests for those operations detect the missing
dependency and assert the clean error message instead — see any test file
with a `HAS_*` flag for the pattern.

Three of the operations (`compress`, `pdf_to_pdfa`, `office_to_pdf`) also
shell out to Ghostscript / LibreOffice. Install them separately if you want
those tests to exercise the real conversion path instead of the
missing-binary error path — neither is required to contribute.

## Adding an operation

One function, one `@register(...)` decorator, in the right `core/ops/*.py`
file (or a new one, if it's a genuinely new kind of thing — see how
`tables.py`/`word.py`/`slides.py` each got their own file for one operation
with a heavy optional dependency). It appears in the CLI, the GUI's tool
tree, and the parameter form automatically — nothing else to wire up.

```python
# core/ops/organise.py
@register(
    id="booklet",
    label="Arrange as booklet",
    category="Organise",
    summary="Reorder pages for folded double-sided printing.",
    params=(Param("sheets", "int", "Sheets per signature", default=4, minimum=1),),
)
def booklet(sources: list[Path], out_dir: Path, sheets: int = 4) -> list[Path]:
    ...
    return [target]
```

Rules `test_every_operation_is_well_formed` (in `tests/test_core.py`) enforces
for you:

- `summary` is a full sentence (ends with `.`)
- `label` starts with a capital letter
- every `choice`-kind param declares its `choices`

A few more that aren't test-enforced but matter:

- The function signature is always `(sources: list[Path], out_dir: Path, **params) -> list[Path]`,
  returning the files it wrote.
- Set `inputs="many"` only if the operation genuinely combines multiple files
  into one logical operation (like `merge`). If it instead needs *distinct
  roles* — a base PDF plus a stamp image, say — use `input_slots` instead
  (see `watermark_image` in `core/ops/annotate.py`) so the GUI can show two
  clearly labeled upload boxes instead of one ambiguous one.
- If the operation needs an external binary (Ghostscript, LibreOffice, ...),
  detect it with `core/ops/_binaries.py`'s `require()` and raise a `ValueError`
  with an install hint — never let the import itself fail.
- If it needs a heavy optional Python dependency, gate the import in a
  `try/except ImportError` inside the function body (see `core/ops/tables.py`)
  and add the dependency to the `extras` group in `pyproject.toml`, not
  `dependencies`.

## Licensing — read this before adding any dependency

The project is Apache-2.0, which only holds up if the dependency graph stays
permissive. See the README's "Licensing" section for the full table and
reasoning, and update `THIRD-PARTY-NOTICES.md` when you add one. Short version:

- MIT / BSD / Apache-2.0 / MPL-2.0 / HPND: fine, add it to `dependencies` (or
  `extras` if it's heavy and only one operation needs it).
- AGPL/GPL tools (Ghostscript, Tesseract, LibreOffice): allowed only as
  **separate processes** invoked via subprocess, never imported directly.
- **PyMuPDF is off-limits** — it's AGPL-3.0, and importing it directly (not
  as a subprocess) would relicense the whole project the moment it's used.

## Testing philosophy

Every operation gets at least one test that exercises its real logic — not
just "it didn't crash." Look at any existing test file for the house style:
build a minimal synthetic PDF by hand (`pypdf.PdfWriter`), run the operation
through `REGISTRY[...]run(...)`, assert something specific about the output
(page count, extracted text, rotation, an embedded image's pixel color —
whatever actually proves the operation did what it claims).

For GUI code, only pure logic gets a pytest (see `tests/test_gui_thumbnails.py`
for the pattern) — Qt widget behavior itself isn't unit-tested in this repo.

## Pull requests

- Keep the diff scoped to what you're actually changing. A new operation
  doesn't need to also refactor the module it lives in.
- Run `pytest` and `ruff check` before opening the PR.
- If you're adding an operation, update the README's operation list and
  count in the same PR.
