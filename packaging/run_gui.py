"""PyInstaller entry point.

app.py itself uses package-relative imports ("from ..core.registry import
..."), which only resolve when Python treats it as part of the `quire`
package -- not when a bundler runs it as a standalone top-level script. This
tiny wrapper imports it properly instead.
"""

from quire.gui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
