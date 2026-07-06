from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src.adapters.sqlite_adapter import SQLiteAdapter
from src.api import service
from src.config.loader import load_source
from src.domain.enums import Act
from src.domain.result import Err


def _load(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    cfg_r = load_source(Path(args.source_dir))
    if isinstance(cfg_r, Err):
        print(f"error: {cfg_r.error.message}", file=sys.stderr)
        return 1

    dt = float(args.dt) if args.dt else time.time()
    act = Act(args.act.upper())

    result = service.load_file(storage, Path(args.data_file), cfg_r.value, dt, act)
    if isinstance(result, Err):
        print(f"error: {result.error.message}", file=sys.stderr)
        return 1

    print(f"loaded {result.value} transaction(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ds", description="data-sources CLI")
    parser.add_argument("--db", default="data.db", help="SQLite database path (default: data.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    load_p = sub.add_parser("load", help="load data from a JSON file")
    load_p.add_argument("source_dir", help="path to source config directory")
    load_p.add_argument("data_file", help="path to JSON data file")
    load_p.add_argument("--dt", help="unix timestamp (default: current time)")
    load_p.add_argument(
        "--act", default="post",
        choices=["post", "patch", "delete"],
        help="action type (default: post)",
    )

    args = parser.parse_args(argv)
    storage = SQLiteAdapter(args.db)

    if args.command == "load":
        return _load(storage, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
