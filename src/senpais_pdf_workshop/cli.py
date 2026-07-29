"""Command line interface.

Not a single subcommand is written by hand -- argparse is built by walking the
registry. Add an operation to core/ops and it appears here automatically.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core.pipeline import Step, run_pipeline
from .core.registry import REGISTRY, categories, load_operations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="senpai", description="Local PDF tools. Nothing leaves your machine."
    )
    subs = parser.add_subparsers(dest="operation", metavar="OPERATION")

    pipeline = subs.add_parser(
        "pipeline",
        help="[Pipeline] Chain operations, feeding each one's output into the next.",
    )
    pipeline.add_argument(
        "steps",
        type=Path,
        help='JSON file: [{"op": "rotate", "params": {"angle": "90"}}, ...]',
    )
    pipeline.add_argument("sources", nargs="+", type=Path, help="Input files")
    pipeline.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path.cwd(),
        help="Output directory (default: current directory)",
    )

    for category, ops in categories().items():
        for op in ops:
            sub = subs.add_parser(op.id, help=f"[{category}] {op.summary}")
            sub.add_argument(
                "sources",
                nargs="+" if op.inputs == "many" else 1,
                type=Path,
                help="Input PDF" + ("s" if op.inputs == "many" else ""),
            )
            sub.add_argument(
                "-o",
                "--out",
                type=Path,
                default=Path.cwd(),
                help="Output directory (default: current directory)",
            )
            for p in op.params:
                flag = f"--{p.name.replace('_', '-')}"
                if p.kind == "bool":
                    sub.add_argument(
                        flag,
                        dest=p.name,
                        action=argparse.BooleanOptionalAction,
                        default=p.default,
                        help=p.help or p.label,
                    )
                else:
                    sub.add_argument(
                        flag,
                        dest=p.name,
                        default=p.default,
                        choices=list(p.choices) or None,
                        type={"int": int, "float": float}.get(p.kind, str),
                        help=p.help or p.label,
                    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_operations()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.operation:
        parser.print_help()
        return 1

    try:
        if args.operation == "pipeline":
            spec = json.loads(args.steps.read_text(encoding="utf-8"))
            steps = [Step(entry["op"], entry.get("params", {})) for entry in spec]
            written = run_pipeline(steps, [Path(s) for s in args.sources], Path(args.out))
        else:
            op = REGISTRY[args.operation]
            values = {p.name: getattr(args, p.name) for p in op.params}
            written = op.run([Path(s) for s in args.sources], Path(args.out), **values)
    except Exception as exc:  # surfaced to the user, not a traceback
        print(f"senpai: {exc}", file=sys.stderr)
        return 2

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
