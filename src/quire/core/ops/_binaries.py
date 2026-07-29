"""Detection helper for the optional external binaries batch-3 ops shell out to."""

from __future__ import annotations

import shutil


def find(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def require(*names: str, feature: str, install_hint: str) -> str:
    path = find(*names)
    if path is None:
        raise ValueError(f"{feature} needs {'/'.join(names)} on PATH. {install_hint}")
    return path
