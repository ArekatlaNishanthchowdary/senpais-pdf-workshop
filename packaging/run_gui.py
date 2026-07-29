"""PyInstaller entry point.

app.py itself uses package-relative imports ("from ..core.registry import
..."), which only resolve when Python treats it as part of the
`senpais_pdf_workshop` package -- not when a bundler runs it as a standalone
top-level script. This tiny wrapper imports it properly instead.
"""

from senpais_pdf_workshop.gui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
