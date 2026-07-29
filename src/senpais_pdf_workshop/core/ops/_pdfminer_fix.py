"""Defensive workaround for a pdfminer.six / ocrmypdf interaction bug.

Importing ocrmypdf (even without calling it) corrupts pdfminer.pdffont's
module-level standard-font metrics table for the rest of the process --
every "Helvetica"-named font opened afterward silently decodes to
"(cid:N)" placeholders instead of real text, with no error raised. Root
cause is inside pdfminer.six/ocrmypdf, not this project's code; reloading
the module resets the table. Ceiling: if a future pdfminer.six version
keys this differently, this stops helping and needs re-diagnosing rather
than blindly kept around. Call this right before any pdfplumber usage.
"""

from __future__ import annotations

import importlib


def reset_pdfminer_font_cache() -> None:
    import pdfminer.pdffont

    importlib.reload(pdfminer.pdffont)
