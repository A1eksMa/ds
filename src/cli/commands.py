from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from src.adapters.sqlite_adapter import SQLiteAdapter
from src.config.loader import load_source
from src.domain.errors import NotFound
from src.domain.result import Err
from src.service import delete as svc_delete
from src.service import get as svc_get
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


def _get(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    params = svc_get.GetParams()
    if args.preset:
        preset_r = svc_get.load_preset(Path(args.preset))
        if isinstance(preset_r, Err):
            print(f"error: {_err_msg(preset_r.error)}", file=sys.stderr)
            return 1
        params = preset_r.value

    params = svc_get.merge_overrides(
        params,
        src_names=args.src,
        lb_names=args.lb,
        dt=float(args.dt) if args.dt else None,
        include_archive=args.archive,
    )

    result = svc_get.run_get(storage, params, now=time.time())
    if isinstance(result, Err):
        print(f"error: {_err_msg(result.error)}", file=sys.stderr)
        return 1

    payloads = result.value  # {source_name: {meta, data}}

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in payloads.items():
            (out_dir / f"{name}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        print(f"wrote {len(payloads)} file(s) to {out_dir}")
        return 0

    if len(payloads) == 1:
        document = next(iter(payloads.values()))
    else:
        document = payloads
    print(json.dumps(document, indent=2, ensure_ascii=False))
    return 0


def _delete(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    target_r = svc_delete.resolve_target(storage, args.src, args.lb)
    if isinstance(target_r, Err):
        print(f"error: {_err_msg(target_r.error)}", file=sys.stderr)
        return 1
    target = target_r.value

    count_r = svc_delete.count_matching(storage, target)
    if isinstance(count_r, Err):
        print(f"error: {_err_msg(count_r.error)}", file=sys.stderr)
        return 1
    count = count_r.value

    if count == 0:
        print("deleted 0 transaction(s)")
        return 0

    if not args.yes:
        what = f"{args.src}.{args.lb}" if args.lb else args.src
        try:
            answer = input(f"Delete {count} transaction(s) for {what} (active + archived)? [y/N] ")
        except (EOFError, OSError):
            # no readable stdin (piped/closed input, or a captured test run) -> never
            # proceed with an irreversible delete just because we couldn't ask
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("aborted", file=sys.stderr)
            return 1

    result = storage.txn_delete(src_id=target.src_id, lb_id=target.lb_id)
    if isinstance(result, Err):
        print(f"error: {_err_msg(result.error)}", file=sys.stderr)
        return 1

    print(f"deleted {result.value} transaction(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ds", description="data-sources CLI")
    parser.add_argument("--db", default="data.db", help="SQLite database path (default: data.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    load_p = sub.add_parser("load", help="load data from a JSON file")
    load_p.add_argument("source_dir", help="path to source config directory")
    load_p.add_argument("data_file", help="path to JSON data file")
    load_p.add_argument("--dt", help="unix timestamp (default: current time)")

    get_p = sub.add_parser("get", help="export folded per-source state as JSON")
    get_p.add_argument("--out", help="output directory (one <source>.json per source); default: stdout")
    get_p.add_argument("--src", action="append", help="source name (repeatable); default: all sources")
    get_p.add_argument("--lb", action="append", help="label name (repeatable); default: all labels")
    get_p.add_argument("--dt", help="unix timestamp cutoff / as-of (default: current time)")
    get_p.add_argument("--preset", help="preset JSON file; its 'query' section supplies the parameters")
    get_p.add_argument("--archive", action="store_true", help="include archived transactions in the fold")

    delete_p = sub.add_parser(
        "delete", help="permanently delete transactions for a source (or one of its labels)"
    )
    delete_p.add_argument("--src", required=True, help="source name")
    delete_p.add_argument("--lb", help="label name; default: the whole source")
    delete_p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    args = parser.parse_args(argv)
    storage = SQLiteAdapter(args.db)

    if args.command == "load":
        return _load(storage, args)
    if args.command == "get":
        return _get(storage, args)
    if args.command == "delete":
        return _delete(storage, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
