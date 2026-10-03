from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from src.adapters.sqlite_adapter import SQLiteAdapter
from src.config.loader import load_source
from src.config.writer import write_source
from src.domain.errors import NotFound
from src.domain.result import Err
from src.service import compact as svc_compact
from src.service import config_sync as svc_config_sync
from src.service import get as svc_get
from src.service import mv as svc_mv
from src.service import selector as svc_selector
from src.service import upload as svc_upload
from src.service.load import load, load_file


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


def _upload(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    cfg_r = load_source(Path(args.source_dir))
    if isinstance(cfg_r, Err):
        print(f"error: {_err_msg(cfg_r.error)}", file=sys.stderr)
        return 1
    cfg = cfg_r.value

    try:
        data = json.loads(Path(args.data_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    strict_r = svc_upload.validate_known_schema(storage, data, cfg)
    if isinstance(strict_r, Err):
        print(f"error: {_err_msg(strict_r.error)}", file=sys.stderr)
        return 1

    dt = float(args.dt) if args.dt else time.time()

    result = load(storage, data, cfg, dt)
    if isinstance(result, Err):
        print(f"error: {_err_msg(result.error)}", file=sys.stderr)
        return 1

    print(f"uploaded {result.value} transaction(s)")
    return 0


def _update(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    cfg_r = load_source(Path(args.source_dir))
    if isinstance(cfg_r, Err):
        print(f"error: {_err_msg(cfg_r.error)}", file=sys.stderr)
        return 1

    sync_r = svc_config_sync.sync_labels(storage, cfg_r.value)
    if isinstance(sync_r, Err):
        print(f"error: {_err_msg(sync_r.error)}", file=sys.stderr)
        return 1
    result = sync_r.value

    write_r = write_source(Path(args.source_dir) / "source.json", result.cfg)
    if isinstance(write_r, Err):
        print(f"error: {_err_msg(write_r.error)}", file=sys.stderr)
        return 1

    if not result.added and not result.removed:
        print("source.json already up to date")
        return 0
    if result.added:
        print(f"added: {', '.join(result.added)}")
    if result.removed:
        print(f"removed: {', '.join(result.removed)}")
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

    if args.cache:
        cache_path = Path(args.cache)
        cache = svc_get.load_cache(cache_path)
        result = svc_get.run_get_cached(storage, params, now=time.time(), cache=cache)
        if isinstance(result, Err):
            print(f"error: {_err_msg(result.error)}", file=sys.stderr)
            return 1
        payloads, new_cache = result.value
        svc_get.save_cache(cache_path, new_cache)
    else:
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


# --- delete / archive: same selector, different terminal action (hard vs soft removal) ---

def _validate_lifecycle_args(args: argparse.Namespace) -> str | None:
    has_cnt = bool(args.cnt)
    has_other = bool(
        args.lb or args.id or args.where or args.dt_from or args.dt_until
        or args.created_from or args.created_until
    )
    if has_cnt and has_other:
        return "--cnt cannot be combined with --lb/--id/--where/--dt-*/--created-*"
    if args.id and args.where:
        return "--id and --where are mutually exclusive"
    if args.where is not None and "=" not in args.where:
        return "--where must be LB=VALUE"
    return None


def _describe_selector(args: argparse.Namespace) -> str:
    if args.cnt:
        return f"{args.src} (cnt {','.join(str(c) for c in args.cnt)})"
    parts = [args.src]
    if args.lb:
        parts.append("lb=" + ",".join(args.lb))
    if args.where:
        parts.append("where " + args.where)
    elif args.id:
        parts.append("id=" + ",".join(args.id))
    if args.dt_from or args.dt_until:
        parts.append(f"dt[{args.dt_from or ''}:{args.dt_until or ''}]")
    if args.created_from or args.created_until:
        parts.append(f"created[{args.created_from or ''}:{args.created_until or ''}]")
    return " ".join(parts)


def _lifecycle_op(storage: SQLiteAdapter, args: argparse.Namespace, verb_past: str, verb_imp: str, action) -> int:
    err = _validate_lifecycle_args(args)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    where = None
    if args.where:
        name, _, value = args.where.partition("=")
        where = (name, value)

    selector_r = svc_selector.resolve_selector(
        storage,
        src_name=args.src,
        lb_names=args.lb,
        id_values=args.id,
        where=where,
        cnts=args.cnt,
        from_dt=float(args.dt_from) if args.dt_from else None,
        until_dt=float(args.dt_until) if args.dt_until else None,
        created_from=float(args.created_from) if args.created_from else None,
        created_until=float(args.created_until) if args.created_until else None,
    )
    if isinstance(selector_r, Err):
        print(f"error: {_err_msg(selector_r.error)}", file=sys.stderr)
        return 1
    selector = selector_r.value

    count_r = svc_selector.count_matching(storage, selector)
    if isinstance(count_r, Err):
        print(f"error: {_err_msg(count_r.error)}", file=sys.stderr)
        return 1
    count = count_r.value

    if count == 0:
        print(f"{verb_past} 0 transaction(s)")
        return 0

    if not args.yes:
        what = _describe_selector(args)
        try:
            answer = input(f"{verb_imp} {count} transaction(s) for {what} (active + archived)? [y/N] ")
        except (EOFError, OSError):
            # no readable stdin (piped/closed input, or a captured test run) -> never
            # proceed with an irreversible/semi-irreversible op just because we couldn't ask
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("aborted", file=sys.stderr)
            return 1

    result = action(
        src_id=selector.src_id, lb_ids=selector.lb_ids, id_ids=selector.id_ids,
        cnts=selector.cnts, from_dt=selector.from_dt, until_dt=selector.until_dt,
        created_from=selector.created_from, created_until=selector.created_until,
    )
    if isinstance(result, Err):
        print(f"error: {_err_msg(result.error)}", file=sys.stderr)
        return 1

    print(f"{verb_past} {result.value} transaction(s)")
    return 0


def _delete(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    return _lifecycle_op(storage, args, "deleted", "Delete", storage.txn_delete)


def _archive(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    return _lifecycle_op(storage, args, "archived", "Archive", storage.txn_archive)


def _unarchive(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    return _lifecycle_op(storage, args, "unarchived", "Unarchive", storage.txn_unarchive)


# --- mv: rename/merge a label across names and/or sources ---

def _mv(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    plan_r = svc_mv.resolve_mv(
        storage, src_name=args.src, lb_name=args.lb,
        to_src_name=args.to_src, to_lb_name=args.to_lb,
    )
    if isinstance(plan_r, Err):
        print(f"error: {_err_msg(plan_r.error)}", file=sys.stderr)
        return 1
    plan = plan_r.value

    count_r = svc_mv.count_matching(storage, plan)
    if isinstance(count_r, Err):
        print(f"error: {_err_msg(count_r.error)}", file=sys.stderr)
        return 1
    count = count_r.value

    what = f"{args.src}.{args.lb} -> {plan.to_src_name}.{plan.to_lb_name}"
    if not args.yes:
        try:
            answer = input(f"Move {count} transaction(s) ({what})? [y/N] ")
        except (EOFError, OSError):
            # no readable stdin (piped/closed input, or a captured test run) -> never
            # proceed with a journal rewrite just because we couldn't ask
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("aborted", file=sys.stderr)
            return 1

    result = svc_mv.apply_mv(storage, plan)
    if isinstance(result, Err):
        print(f"error: {_err_msg(result.error)}", file=sys.stderr)
        return 1

    note = "merged into existing label" if plan.into_lb_id is not None else "new label"
    print(f"moved {result.value} transaction(s): {what} ({note})")
    return 0


# --- compact: find transactions that repeat the value already in effect, soft/hard-remove them ---

def _label_name(storage: SQLiteAdapter, lb_id) -> str:
    r = storage.lb_get(lb_id)
    return r.value.name if not isinstance(r, Err) else f"lb#{int(lb_id)}"


def _id_value(storage: SQLiteAdapter, id_id) -> str:
    r = storage.id_get(id_id)
    return r.value if not isinstance(r, Err) else f"id#{int(id_id)}"


def _val_display(storage: SQLiteAdapter, val_id: int) -> str:
    if val_id == 0:
        return "<deleted>"
    r = storage.val_get(val_id)
    return r.value if not isinstance(r, Err) else f"val#{val_id}"


def _compact(storage: SQLiteAdapter, args: argparse.Namespace) -> int:
    src_r = svc_selector.resolve_src(storage, args.src)
    if isinstance(src_r, Err):
        print(f"error: {_err_msg(src_r.error)}", file=sys.stderr)
        return 1
    src_id = src_r.value.src_id

    lb_ids = None
    if args.lb:
        lb_ids_r = svc_selector.resolve_lb_ids(storage, src_id, args.lb)
        if isinstance(lb_ids_r, Err):
            print(f"error: {_err_msg(lb_ids_r.error)}", file=sys.stderr)
            return 1
        lb_ids = lb_ids_r.value

    id_ids = None
    if args.id:
        id_ids_r = svc_selector.resolve_id_ids(storage, args.id)
        if isinstance(id_ids_r, Err):
            print(f"error: {_err_msg(id_ids_r.error)}", file=sys.stderr)
            return 1
        id_ids = id_ids_r.value

    dup_r = svc_compact.find_duplicates(
        storage, src_id, lb_ids, id_ids,
        from_dt=float(args.dt_from) if args.dt_from else None,
        until_dt=float(args.dt_until) if args.dt_until else None,
    )
    if isinstance(dup_r, Err):
        print(f"error: {_err_msg(dup_r.error)}", file=sys.stderr)
        return 1
    duplicates = dup_r.value

    verb_past, verb_imp = ("deleted", "Delete") if args.hard else ("archived", "Archive")
    targets = duplicates if args.hard else [d for d in duplicates if d.active]
    count = len(targets)

    if count == 0:
        print(f"{verb_past} 0 duplicate transaction(s)")
        return 0

    if not args.yes:
        print(f"Found {count} duplicate transaction(s), e.g.:")
        for d in targets[:5]:
            lb_name = _label_name(storage, d.lb_id)
            id_value = _id_value(storage, d.id_id)
            val_display = _val_display(storage, d.val)
            print(f"  {args.src}.{lb_name}.{id_value} @ dt={d.dt} = {val_display}")
        if count > 5:
            print(f"  ... and {count - 5} more")
        try:
            answer = input(f"{verb_imp} {count} duplicate transaction(s)? [y/N] ")
        except (EOFError, OSError):
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("aborted", file=sys.stderr)
            return 1

    cnts = [d.cnt for d in targets]
    action = storage.txn_delete if args.hard else storage.txn_archive
    result = action(cnts=cnts)
    if isinstance(result, Err):
        print(f"error: {_err_msg(result.error)}", file=sys.stderr)
        return 1

    print(f"{verb_past} {result.value} duplicate transaction(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ds", description="data-sources CLI")
    parser.add_argument("--db", default="data.db", help="SQLite database path (default: data.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    load_p = sub.add_parser("load", help="load data from a JSON file")
    load_p.add_argument("source_dir", help="path to source config directory")
    load_p.add_argument("data_file", help="path to JSON data file")
    load_p.add_argument("--dt", help="unix timestamp (default: current time)")

    upload_p = sub.add_parser(
        "upload",
        help="like load, but reject the whole file if it has an undeclared/unknown label "
             "or a value that doesn't parse under its declared type",
    )
    upload_p.add_argument("source_dir", help="path to source config directory")
    upload_p.add_argument("data_file", help="path to JSON data file")
    upload_p.add_argument("--dt", help="unix timestamp (default: current time)")

    update_p = sub.add_parser(
        "update",
        help="refresh source.json's label inventory against the database's current reality",
    )
    update_p.add_argument("source_dir", help="path to source config directory")

    get_p = sub.add_parser("get", help="export folded per-source state as JSON")
    get_p.add_argument("--out", help="output directory (one <source>.json per source); default: stdout")
    get_p.add_argument("--src", action="append", help="source name (repeatable); default: all sources")
    get_p.add_argument("--lb", action="append", help="label name (repeatable); default: all labels")
    get_p.add_argument("--dt", help="unix timestamp cutoff / as-of (default: current time)")
    get_p.add_argument("--preset", help="preset JSON file; its 'query' section supplies the parameters")
    get_p.add_argument("--archive", action="store_true", help="include archived transactions in the fold")
    get_p.add_argument(
        "--cache",
        help="incremental fold cache file (read if present, always rewritten); "
             "speeds up repeated `ds get` calls when the source(s) only grew by "
             "plain loads since the last call -- see docs/reference/cli.md#ds-get",
    )

    def _add_lifecycle_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--src", required=True, help="source name")
        p.add_argument("--lb", action="append", help="label name (repeatable); default: every label")
        p.add_argument("--id", action="append", help="key value (repeatable); default: every key")
        p.add_argument(
            "--where", metavar="LB=VALUE",
            help="select keys whose current (folded) value of label LB equals VALUE; "
                 "mutually exclusive with --id",
        )
        p.add_argument(
            "--cnt", action="append", type=int,
            help="specific transaction(s) by counter number (repeatable); standalone -- "
                 "not combinable with --lb/--id/--where/--dt-*/--created-*",
        )
        p.add_argument("--dt-from", help="business time (dt) lower bound, unix timestamp")
        p.add_argument("--dt-until", help="business time (dt) upper bound, unix timestamp")
        p.add_argument("--created-from", help="load time (created_at) lower bound, unix timestamp")
        p.add_argument("--created-until", help="load time (created_at) upper bound, unix timestamp")
        p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    delete_p = sub.add_parser(
        "delete", help="permanently delete matching transactions from both transactions and transactions_archive"
    )
    _add_lifecycle_args(delete_p)

    archive_p = sub.add_parser(
        "archive", help="move matching active transactions into transactions_archive"
    )
    _add_lifecycle_args(archive_p)

    unarchive_p = sub.add_parser(
        "unarchive", help="move matching archived transactions back into transactions"
    )
    _add_lifecycle_args(unarchive_p)

    mv_p = sub.add_parser(
        "mv",
        help="rename/merge a label across names and/or sources -- rewrites lb/src on "
             "every matching transaction (active + archived)",
    )
    mv_p.add_argument("--src", required=True, help="current source name")
    mv_p.add_argument("--lb", required=True, help="current label name")
    mv_p.add_argument(
        "--to-src",
        help="destination source name; default: same as --src. Created automatically if it "
             "doesn't exist yet",
    )
    mv_p.add_argument(
        "--to-lb", required=True,
        help="destination label name. Created automatically if new; if it already exists, "
             "its history is merged with --lb's",
    )
    mv_p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    compact_p = sub.add_parser(
        "compact",
        help="find transactions that repeat the value already in effect (no-op history) and archive/delete them",
    )
    compact_p.add_argument("--src", required=True, help="source name")
    compact_p.add_argument("--lb", action="append", help="label name (repeatable); default: every label")
    compact_p.add_argument("--id", action="append", help="key value (repeatable); default: every key")
    compact_p.add_argument(
        "--dt-from",
        help="business time (dt) lower bound, unix timestamp -- the first transaction found "
             "at/after this bound, per key, is never flagged, even if it would duplicate "
             "something earlier that falls outside the window",
    )
    compact_p.add_argument("--dt-until", help="business time (dt) upper bound, unix timestamp")
    compact_p.add_argument("--hard", action="store_true", help="physically delete duplicates instead of archiving them")
    compact_p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    args = parser.parse_args(argv)
    storage = SQLiteAdapter(args.db)

    if args.command == "load":
        return _load(storage, args)
    if args.command == "upload":
        return _upload(storage, args)
    if args.command == "update":
        return _update(storage, args)
    if args.command == "get":
        return _get(storage, args)
    if args.command == "delete":
        return _delete(storage, args)
    if args.command == "archive":
        return _archive(storage, args)
    if args.command == "unarchive":
        return _unarchive(storage, args)
    if args.command == "mv":
        return _mv(storage, args)
    if args.command == "compact":
        return _compact(storage, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
