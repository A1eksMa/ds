from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src.adapters.sqlite_adapter import SQLiteAdapter
from src.config.loader import load_source
from src.domain.errors import NotFound
from src.domain.result import Err
from src.service.load import load_file


def _err_msg(error) -> str:
    if isinstance(error, NotFound):
        return f"{error.entity} not found: {error.key}"
    return error.message


def _load(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    cfg_r = load_source(Path(args.source_dir))
    if isinstance(cfg_r, Err):
        print(f"error: {_err_msg(cfg_r.error)}", file=sys.stderr)
        return 1

    dt = float(args.dt) if args.dt else time.time()

    result = load_file(storage, Path(args.data_file), cfg_r.value, dt)
    if isinstance(result, Err):
        print(f"error: {_err_msg(result.error)}", file=sys.stderr)
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

    args = parser.parse_args(argv)
    storage = SQLiteAdapter(args.db)

    if args.command == "load":
        return _load(storage, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
