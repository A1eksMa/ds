from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional, Union

from src.domain.entities import IdId, LbId, SrcId, Transaction, ValId
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


def fold_source(txns: List[Transaction]) -> Dict[tuple, int]:
    """Collapse a source's transaction list to one winner per (lb_id, id_id).

    Level 1 rule (see docs/decisions/0006-fold-order-dt-cnt.md): the transaction
    with the greatest (dt, cnt) wins. Returns {(lb_id, id_id): val_id}; val_id 0
    means the winning op was a DELETE.
    """
    winners: Dict[tuple, Transaction] = {}
    for t in txns:
        key = (int(t.lb), int(t.id))
        cur = winners.get(key)
        if cur is None or (t.dt, int(t.cnt)) > (cur.dt, int(cur.cnt)):
            winners[key] = t
    return {key: int(t.val) for key, t in winners.items()}


# --- per-source export ------------------------------------------------------


def build_source(
    storage: StoragePort,
    src,
    label_names: Optional[List[str]],
    effective_dt: float,
    include_archive: bool,
    now: float,
) -> Union[Ok[dict], _Err]:
    """Build the {meta, data} payload for one source.

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

    val_cache: Dict[int, str] = {}
    rows_by_id: Dict[int, Dict[str, Optional[str]]] = {}
    for (lb_id, id_id), val_id in folded.items():
        row = rows_by_id.setdefault(id_id, {})
        if val_id == 0:
            row[lbid_to_name[lb_id]] = None
            continue
        if val_id not in val_cache:
            vr = storage.val_get(ValId(val_id))
            if isinstance(vr, Err):
                return vr
            val_cache[val_id] = vr.value
        row[lbid_to_name[lb_id]] = val_cache[val_id]

    key_col = key_name or "id"
    data: List[dict] = []
    for id_id, cols in rows_by_id.items():
        ir = storage.id_get(IdId(id_id))
        if isinstance(ir, Err):
            return ir
        ordered: Dict[str, Optional[str]] = {key_col: ir.value}
        for name in sorted(cols):
            ordered[name] = cols[name]
        data.append(ordered)
    data.sort(key=lambda r: r[key_col])

    return Ok({
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
    })


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
