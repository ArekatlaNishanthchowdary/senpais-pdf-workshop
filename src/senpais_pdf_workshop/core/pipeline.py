"""Chain operations: run a sequence of registered ops, feeding each step's
output files into the next step's input. Every step still goes through
Operation.run(), so arity/required-param validation applies exactly as it
would for a single op -- the pipeline itself only threads sources through.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .registry import REGISTRY


@dataclass(frozen=True)
class Step:
    """One stage of a pipeline: which operation, and its parameters."""

    op_id: str
    params: dict[str, Any] = field(default_factory=dict)


def run_pipeline(steps: list[Step], sources: list[Path], out_dir: Path) -> list[Path]:
    """Run each step in order, using one step's output as the next step's
    input. Intermediate steps write to a scratch directory that's cleaned up
    afterward; only the final step's output lands in `out_dir`."""
    if not steps:
        raise ValueError("A pipeline needs at least one step.")
    for step in steps:
        if step.op_id not in REGISTRY:
            raise ValueError(f"Unknown operation: {step.op_id}")

    current = sources
    with tempfile.TemporaryDirectory(prefix="senpai-pipeline-") as tmp:
        for index, step in enumerate(steps):
            op = REGISTRY[step.op_id]
            is_last = index == len(steps) - 1
            step_out = out_dir if is_last else Path(tmp) / f"step{index}"
            current = op.run(current, step_out, **step.params)
    return current
