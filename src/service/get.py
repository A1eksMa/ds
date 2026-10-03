from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from src.domain.entities import CntId, IdId, LbId, SrcId, Transaction, ValId
from src.domain.errors import NotFound, StorageError, ValidationError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort

# --- Result aliases (read-only path: no IntegrityError) --------------------------

_Err = Union[Err[StorageError], Err[NotFound], Err[ValidationError]]


@dataclass(frozen=True)
class GetParams:
    """Parameters for a `ds get` run.

    sources           -- source names to export; None => every source in the DB.
    labels_by_source  -- per-source label whitelist; overrides `labels` for that source.
    labels            -- fallback label whitelist for sources without an explicit
                         entry; None => all (non-key) labels of the source.
    dt                -- business-time cutoff (unix seconds); None => "now" (the
                         value passed to run_get).
    include_archive   -- fold archived transactions in as well.
    """
    sources: Optional[List[str]] = None
    labels_by_source: Dict[str, List[str]] = field(default_factory=dict)
    labels: Optional[List[str]] = None
    dt: Optional[float] = None
    include_archive: bool = False


# --- preset loading ------------------------------------------------------------


def load_preset(path: Path) -> Union[Ok[GetParams], _Err]:
    """Read a preset file and pull its `query` section into GetParams.

    Accepted shapes (all keys optional)::

        { "query": {
            "as_of": <unix ts> | null,
            "include_archive": <bool>,
            "labels": [<name>, ...],
            "sources": { "CRM": { "labels": [<name>, ...] }, ... }
                        | [ "CRM", "ERP" ]
        } }

    A bare query object (no "query" wrapper) is also accepted. Everything the
    getter does not understand (e.g. a "view" section) is ignored.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Err(StorageError(str(exc)))

    query = raw.get("query", raw) if isinstance(raw, dict) else None
    if not isinstance(query, dict):
        return Err(ValidationError(field="preset", message="'query' must be an object"))

    as_of = query.get("as_of")
    dt = float(as_of) if as_of is not None else None
    include_archive = bool(query.get("include_archive", False))

    top_labels = query.get("labels")
    labels = [str(x) for x in top_labels] if isinstance(top_labels, list) else None

    src_field = query.get("sources")
    sources: Optional[List[str]] = None
    labels_by_source: Dict[str, List[str]] = {}
    if isinstance(src_field, dict):
        sources = list(src_field.keys())
        for name, spec in src_field.items():
            if isinstance(spec, dict) and isinstance(spec.get("labels"), list):
                labels_by_source[name] = [str(x) for x in spec["labels"]]
    elif isinstance(src_field, list):
        sources = [str(x) for x in src_field]
    elif src_field is not None:
        return Err(ValidationError(
            field="preset", message="'sources' must be an object or an array",
        ))

    return Ok(GetParams(
        sources=sources,
        labels_by_source=labels_by_source,
        labels=labels,
        dt=dt,
        include_archive=include_archive,
    ))


def merge_overrides(
    params: GetParams,
    *,
    src_names: Optional[List[str]] = None,
    lb_names: Optional[List[str]] = None,
    dt: Optional[float] = None,
    include_archive: bool = False,
) -> GetParams:
    """Apply CLI flags on top of a preset. Explicit flags win.

    - `--src` replaces the source list (keeping only matching per-source label
      whitelists).
    - `--lb` sets a global label whitelist and drops per-source ones.
    - `--dt` replaces the cutoff.
    - `--archive` can only turn archive inclusion *on*.
    """
    sources = params.sources
    labels_by_source = dict(params.labels_by_source)
    labels = params.labels

    if src_names:
        sources = list(src_names)
        labels_by_source = {k: v for k, v in labels_by_source.items() if k in src_names}
    if lb_names:
        labels = list(lb_names)
        labels_by_source = {}

    return replace(
        params,
        sources=sources,
        labels_by_source=labels_by_source,
        labels=labels,
        dt=dt if dt is not None else params.dt,
        include_archive=include_archive or params.include_archive,
    )


# --- Level 1 fold ------------------------------------------------------------

# (lb_id, id_id) -> (dt, cnt, val_id) of the winning transaction. val_id 0 means
# the winning op was a DELETE. Keeping (dt, cnt) alongside val_id (rather than
# collapsing straight to val_id, as the public {meta, data} payload does) is
# what makes this shape reusable as a merge seed -- see SourceCacheEntry below.
_Winners = Dict[Tuple[int, int], Tuple[float, int, int]]


def fold_source(txns: List[Transaction], seed: Optional[_Winners] = None) -> _Winners:
    """Collapse a source's transaction list to one winner per (lb_id, id_id).

    Level 1 rule (see docs/decisions/0006-fold-order-dt-cnt.md): the transaction
    with the greatest (dt, cnt) wins. Returns {(lb_id, id_id): (dt, cnt, val_id)}.

    `seed` -- an existing winners mapping (e.g. from a fold cache) to merge
    `txns` into instead of folding from scratch. The merge is order-independent:
    each candidate is compared only against the current winner for its key, so
    callers may pass `txns` in any order, including out-of-order business time
    (backdated corrections) -- see docs/decisions/0010-incremental-fold-cache.md.
    """
    winners: _Winners = dict(seed) if seed else {}
    for t in txns:
        key = (int(t.lb), int(t.id))
        cand = (t.dt, int(t.cnt), int(t.val))
        cur = winners.get(key)
        if cur is None or (cand[0], cand[1]) > (cur[0], cur[1]):
            winners[key] = cand
    return winners


@dataclass(frozen=True)
class SourceCacheEntry:
    """Incremental-fold cache for one source, written and consumed only by
    `ds get --cache` -- opaque to every other caller. Deliberately NOT the
    public `{meta, data}` payload: that format collapses each cell down to its
    resolved value and drops the (dt, cnt) it won on, which is exactly the
    information `fold_source`'s merge needs. See
    docs/decisions/0010-incremental-fold-cache.md.

    `struct_version`/`labels`/`include_archive` pin the exact query shape this
    cache is valid for; `as_of` is the previous effective_dt (the lower bound
    for the "did anything newly fall into dt range" catch-up query -- see
    `_build_source`); `max_cnt` is the watermark for the "what's new" query.
    """
    struct_version: int
    max_cnt: int
    as_of: float
    include_archive: bool
    labels: Tuple[str, ...]
    winners: _Winners


def _cache_usable(
    entry: Optional[SourceCacheEntry],
    struct_version: int,
    labels: Tuple[str, ...],
    include_archive: bool,
    effective_dt: float,
) -> bool:
    return (
        entry is not None
        and entry.struct_version == struct_version
        and entry.include_archive == include_archive
        and entry.labels == labels
        and effective_dt >= entry.as_of
    )


def cache_entry_to_json(entry: SourceCacheEntry) -> dict:
    return {
        "struct_version": entry.struct_version,
        "max_cnt": entry.max_cnt,
        "as_of": entry.as_of,
        "include_archive": entry.include_archive,
        "labels": list(entry.labels),
        "winners": [
            [lb, id_, dt, cnt, val]
            for (lb, id_), (dt, cnt, val) in sorted(entry.winners.items())
        ],
    }


def cache_entry_from_json(obj: object) -> Optional[SourceCacheEntry]:
    """Tolerant parse: any shape mismatch -> None, i.e. "no usable cache for
    this source" -- callers fall back to a full rebuild, never a hard error.
    Covers a hand-edited/corrupt file and a cache from a future `ds` version
    with a different cache shape alike."""
    if not isinstance(obj, dict):
        return None
    try:
        winners = {
            (int(lb), int(id_)): (float(dt), int(cnt), int(val))
            for lb, id_, dt, cnt, val in obj["winners"]
        }
        return SourceCacheEntry(
            struct_version=int(obj["struct_version"]),
            max_cnt=int(obj["max_cnt"]),
            as_of=float(obj["as_of"]),
            include_archive=bool(obj["include_archive"]),
            labels=tuple(str(x) for x in obj["labels"]),
            winners=winners,
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_cache(path: Path) -> Dict[str, SourceCacheEntry]:
    """Read a `ds get --cache` file. Missing/corrupt/unreadable -> {} (treated
    exactly like "no cache yet" -- every source falls back to a full rebuild)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, SourceCacheEntry] = {}
    for name, obj in raw.items():
        entry = cache_entry_from_json(obj)
        if entry is not None:
            out[name] = entry
    return out


def save_cache(path: Path, cache: Dict[str, SourceCacheEntry]) -> None:
    doc = {name: cache_entry_to_json(entry) for name, entry in cache.items()}
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# --- per-source export ------------------------------------------------------


def _build_source(
    storage: StoragePort,
    src,
    label_names: Optional[List[str]],
    effective_dt: float,
    include_archive: bool,
    now: float,
    cache_entry: Optional[SourceCacheEntry],
) -> Union[Ok[Tuple[dict, SourceCacheEntry]], _Err]:
    """Build the {meta, data} payload for one source, optionally seeded from a
    prior fold (`cache_entry`). Returns (payload, updated_cache_entry) -- the
    latter is always produced, even when no cache was passed in or usable, so
    callers can persist it for next time regardless of which path ran.

    `data` is a wide table: one object per id, keyed by the source's key label
    plus the selected labels. A label value of None means the last op was a
    DELETE; a key simply absent from a row means that (label, id) pair had no
    transaction in the slice.
    """
    lbs_r = storage.lb_list(SrcId(src.src_id))
    if isinstance(lbs_r, Err):
        return lbs_r
    name_to_lbid = {lb.name: int(lb.lb_id) for lb in lbs_r.value}

    key_lbid = int(src.key_label) if src.key_label is not None else None
    key_name = next((n for n, i in name_to_lbid.items() if i == key_lbid), None)

    if label_names is None:
        selected = {n: i for n, i in name_to_lbid.items() if i != key_lbid}
    else:
        selected = {}
        for n in label_names:
            if n == key_name:
                continue
            if n not in name_to_lbid:
                return Err(NotFound(entity="Label", key=f"{src.name}.{n}"))
            selected[n] = name_to_lbid[n]
    lbid_to_name = {i: n for n, i in selected.items()}
    selected_lbids = set(selected.values())
    labels_key = tuple(sorted(selected.keys()))
    struct_version = int(getattr(src, "struct_version", 0))

    usable = _cache_usable(cache_entry, struct_version, labels_key, include_archive, effective_dt)
    if usable:
        lb_filter = [LbId(i) for i in selected_lbids] if selected_lbids else None
        # Two catch-up queries, merged together (fold_source's merge is
        # order-independent, so overlap between them is harmless):
        #  (a) truly new transactions -- cnt advanced since the cache was taken;
        #  (b) transactions that already existed back then but were excluded
        #      from that fold purely because their business time (dt) was
        #      still beyond the old as_of -- e.g. a future-dated scheduled
        #      change. Their cnt can be *lower* than the cache's watermark
        #      (interleaved with other, already-folded rows in the same
        #      batch), so (a) alone would permanently miss them once their dt
        #      finally comes into range. See docs/decisions/0010-incremental-fold-cache.md.
        new_r = storage.txn_query(
            src_id=SrcId(src.src_id), lb_ids=lb_filter,
            from_cnt=CntId(cache_entry.max_cnt), until_dt=effective_dt,
            include_archive=include_archive,
        )
        if isinstance(new_r, Err):
            return new_r
        pending_r = storage.txn_query(
            src_id=SrcId(src.src_id), lb_ids=lb_filter,
            from_dt=cache_entry.as_of, until_dt=effective_dt,
            include_archive=include_archive,
        )
        if isinstance(pending_r, Err):
            return pending_r
        delta = new_r.value + pending_r.value
        folded = fold_source(delta, seed=cache_entry.winners)
        gen_max_cnt = max([cache_entry.max_cnt] + [int(t.cnt) for t in delta])
    else:
        txns_r = storage.txn_query(
            src_id=SrcId(src.src_id),
            until_dt=effective_dt,
            include_archive=include_archive,
        )
        if isinstance(txns_r, Err):
            return txns_r
        txns = txns_r.value
        gen_max_cnt = max((int(t.cnt) for t in txns), default=0)
        folded = fold_source([t for t in txns if int(t.lb) in selected_lbids])

    # Batched instead of one id_get/val_get per cell: at publish scale the
    # winners dict (and hence this resolution step) is O(every current row in
    # the source), independent of whether the fold itself took the cached
    # fast path above -- one id_get/val_get round trip per row dominated a
    # 60k-row benchmark even with the fold fully cached (see
    # docs/decisions/0010-incremental-fold-cache.md).
    val_ids_needed = {val_id for (_lb, _id), (_dt, _cnt, val_id) in folded.items() if val_id != 0}
    val_cache_r = storage.val_get_many([ValId(v) for v in val_ids_needed])
    if isinstance(val_cache_r, Err):
        return val_cache_r
    val_cache = val_cache_r.value

    rows_by_id: Dict[int, Dict[str, Optional[str]]] = {}
    for (lb_id, id_id), (_dt, _cnt, val_id) in folded.items():
        row = rows_by_id.setdefault(id_id, {})
        row[lbid_to_name[lb_id]] = None if val_id == 0 else val_cache.get(val_id)

    key_col = key_name or "id"
    id_names_r = storage.id_get_many([IdId(i) for i in rows_by_id])
    if isinstance(id_names_r, Err):
        return id_names_r
    id_names = id_names_r.value

    label_order = sorted(selected.keys())  # precomputed once, not per row
    data: List[dict] = []
    for id_id, cols in rows_by_id.items():
        ordered: Dict[str, Optional[str]] = {key_col: id_names.get(id_id)}
        for name in label_order:
            if name in cols:
                ordered[name] = cols[name]
        data.append(ordered)
    data.sort(key=lambda r: r[key_col])

    payload = {
        "meta": {
            "name": src.name,
            "key": key_name,
            "as_of": effective_dt,
            "generated_at": now,
            "gen_max_cnt": gen_max_cnt,
            "include_archive": include_archive,
            "rows": len(data),
            "labels": sorted(selected.keys()),
        },
        "data": data,
    }
    new_entry = SourceCacheEntry(
        struct_version=struct_version,
        max_cnt=gen_max_cnt,
        as_of=effective_dt,
        include_archive=include_archive,
        labels=labels_key,
        winners=folded,
    )
    return Ok((payload, new_entry))


def build_source(
    storage: StoragePort,
    src,
    label_names: Optional[List[str]],
    effective_dt: float,
    include_archive: bool,
    now: float,
) -> Union[Ok[dict], _Err]:
    """Build the {meta, data} payload for one source -- always a full fold,
    no cache. See `_build_source` for the cache-seeded variant used by
    `run_get_cached`."""
    result = _build_source(
        storage, src, label_names, effective_dt, include_archive, now,
        cache_entry=None,
    )
    if isinstance(result, Err):
        return result
    payload, _entry = result.value
    return Ok(payload)


def run_get(
    storage: StoragePort,
    params: GetParams,
    now: float,
) -> Union[Ok[Dict[str, dict]], _Err]:
    """Resolve params and build a {source_name: {meta, data}} mapping."""
    srcs_r = storage.src_list()
    if isinstance(srcs_r, Err):
        return srcs_r
    by_name = {s.name: s for s in srcs_r.value}

    names = params.sources if params.sources is not None else [s.name for s in srcs_r.value]
    effective_dt = params.dt if params.dt is not None else now

    out: Dict[str, dict] = {}
    for name in names:
        if name not in by_name:
            return Err(NotFound(entity="Source", key=name))
        label_names = params.labels_by_source.get(name, params.labels)
        result = build_source(
            storage, by_name[name], label_names,
            effective_dt, params.include_archive, now,
        )
        if isinstance(result, Err):
            return result
        out[name] = result.value
    return Ok(out)


def run_get_cached(
    storage: StoragePort,
    params: GetParams,
    now: float,
    cache: Dict[str, SourceCacheEntry],
) -> Union[Ok[Tuple[Dict[str, dict], Dict[str, SourceCacheEntry]]], _Err]:
    """Like `run_get`, but seeds/updates an incremental fold cache per source.

    `cache` -- {source_name: SourceCacheEntry}, typically round-tripped from
    `ds get --cache`'s JSON file via `load_cache`; pass {} on the first call
    for a given cache file. Returns (payloads, updated_cache) with one cache
    entry per processed source, whether or not its cached entry was usable --
    always safe to persist via `save_cache`.
    """
    srcs_r = storage.src_list()
    if isinstance(srcs_r, Err):
        return srcs_r
    by_name = {s.name: s for s in srcs_r.value}

    names = params.sources if params.sources is not None else [s.name for s in srcs_r.value]
    effective_dt = params.dt if params.dt is not None else now

    out: Dict[str, dict] = {}
    new_cache: Dict[str, SourceCacheEntry] = {}
    for name in names:
        if name not in by_name:
            return Err(NotFound(entity="Source", key=name))
        label_names = params.labels_by_source.get(name, params.labels)
        result = _build_source(
            storage, by_name[name], label_names,
            effective_dt, params.include_archive, now,
            cache_entry=cache.get(name),
        )
        if isinstance(result, Err):
            return result
        payload, entry = result.value
        out[name] = payload
        new_cache[name] = entry
    return Ok((out, new_cache))
