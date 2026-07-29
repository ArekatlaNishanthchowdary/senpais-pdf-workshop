"""The operation registry.

Every PDF operation in Senpai's Pdf Workshop is declared here as data: what it's called, what
parameters it takes, what it consumes and produces. The CLI and the GUI are both
*generated* from this registry, so adding an operation means writing one function
and one decorator -- never touching the interface code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

ParamKind = Literal[
    "int",
    "float",
    "str",
    "bool",
    "choice",
    "page_range",  # "1-3,7,9-" style selector
    "password",
    "file",
    "directory",
]

Arity = Literal["one", "many"]


@dataclass(frozen=True)
class Param:
    """One user-supplied argument to an operation."""

    name: str
    kind: ParamKind
    label: str
    default: Any = None
    choices: tuple[str, ...] = ()
    help: str = ""
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class InputSlot:
    """One labeled group of input files, for operations that mix arities or
    formats -- e.g. any number of PDFs plus exactly one stamp image. Front
    ends that don't understand slots can ignore this and fall back to
    `inputs`/`input_formats` on the whole file list instead."""

    name: str
    label: str
    arity: Arity = "one"
    formats: tuple[str, ...] = (".pdf",)


@dataclass(frozen=True)
class Operation:
    """A single PDF operation, described well enough to build a UI from."""

    id: str
    label: str
    category: str
    summary: str
    fn: Callable[..., list[Path]]
    params: tuple[Param, ...] = ()
    inputs: Arity = "one"
    outputs: Arity = "one"
    input_formats: tuple[str, ...] = (".pdf",)
    input_slots: tuple[InputSlot, ...] = ()

    def run(self, sources: list[Path], out_dir: Path, **kwargs: Any) -> list[Path]:
        """Validate arity, fill defaults, then dispatch to the implementation."""
        if self.inputs == "one" and len(sources) != 1:
            raise ValueError(f"{self.label} takes exactly one input file.")
        if not sources:
            raise ValueError(f"{self.label} needs at least one input file.")

        resolved = {p.name: kwargs.get(p.name, p.default) for p in self.params}
        for p in self.params:
            if p.required and resolved[p.name] in (None, ""):
                raise ValueError(f"{self.label} requires {p.label}.")

        out_dir.mkdir(parents=True, exist_ok=True)
        return self.fn(sources, out_dir, **resolved)


REGISTRY: dict[str, Operation] = {}


def register(
    *,
    id: str,
    label: str,
    category: str,
    summary: str,
    params: tuple[Param, ...] = (),
    inputs: Arity = "one",
    outputs: Arity = "one",
    input_formats: tuple[str, ...] = (".pdf",),
    input_slots: tuple[InputSlot, ...] = (),
) -> Callable:
    """Decorator that adds an operation to the registry."""

    def wrap(fn: Callable[..., list[Path]]) -> Callable[..., list[Path]]:
        if id in REGISTRY:
            raise RuntimeError(f"Duplicate operation id: {id}")
        REGISTRY[id] = Operation(
            id=id,
            label=label,
            category=category,
            summary=summary,
            fn=fn,
            params=params,
            inputs=inputs,
            outputs=outputs,
            input_formats=input_formats,
            input_slots=input_slots,
        )
        return fn

    return wrap


def categories() -> dict[str, list[Operation]]:
    """Operations grouped by category, for menu and sidebar construction."""
    grouped: dict[str, list[Operation]] = {}
    for op in REGISTRY.values():
        grouped.setdefault(op.category, []).append(op)
    for ops in grouped.values():
        ops.sort(key=lambda o: o.label)
    return dict(sorted(grouped.items()))


def load_operations() -> None:
    """Import every module under core.ops so the decorators fire."""
    import importlib
    import pkgutil

    from . import ops

    for mod in pkgutil.iter_modules(ops.__path__):
        importlib.import_module(f"{ops.__name__}.{mod.name}")
