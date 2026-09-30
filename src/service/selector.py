from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

from src.domain.entities import CntId, IdId, LbId, SrcId, ValId
from src.domain.errors import NotFound, StorageError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort
from src.service.get import fold_source

_Err = Union[Err[StorageError], Err[NotFound]]


@dataclass(frozen=True)
class Selector:
    """What `ds delete`/`ds archive` (soft vs hard removal of the same rows)
    act on. lb_ids/id_ids: None = every one for the source; an explicitly
    empty list means "matches nothing" (e.g. a --where condition with no
    hits). cnts, when set, is a standalone mode -- lb_ids/id_ids/date ranges
    are not applied alongside it (see resolve_selector)."""
    src_id: SrcId
    lb_ids: Optional[List[LbId]] = None
    id_ids: Optional[List[IdId]] = None
    cnts: Optional[List[CntId]] = None
    from_dt: Optional[float] = None
    until_dt: Optional[float] = None
    created_from: Optional[float] = None
    created_until: Optional[float] = None


def resolve_src(storage: StoragePort, src_name: str):
    """Side-effect-free name -> Src, shared with src/service/compact.py."""
    srcs_r = storage.src_list()
    if isinstance(srcs_r, Err):
        return srcs_r
    src = next((s for s in srcs_r.value if s.name == src_name), None)
    if src is None:
        return Err(NotFound(entity="Source", key=src_name))
    return Ok(src)


def resolve_lb_ids(storage: StoragePort, src_id: SrcId, lb_names: List[str]):
    """Side-effect-free names -> LbIds, shared with src/service/compact.py."""
    lbs_r = storage.lb_list(src_id)
    if isinstance(lbs_r, Err):
        return lbs_r
    by_name = {lb.name: lb.lb_id for lb in lbs_r.value}
    out: List[LbId] = []
    for name in lb_names:
        if name not in by_name:
            return Err(NotFound(entity="Label", key=name))
        out.append(LbId(by_name[name]))
    return Ok(out)


def resolve_id_ids(storage: StoragePort, id_values: List[str]):
    """Side-effect-free values -> IdIds, shared with src/service/compact.py."""
    out: List[IdId] = []
    for value in id_values:
        r = storage.id_lookup(value)
        if isinstance(r, Err):
            return r
        if r.value is None:
            return Err(NotFound(entity="Id", key=value))
        out.append(r.value)
    return Ok(out)


def _resolve_where(storage: StoragePort, src_id: SrcId, lb_name: str, target: str):
    """--where LB=VALUE: fold LB (Level 1, active+archived, as of now) and
    collect every id whose current value equals `target`. May resolve to an
    empty list -- that's a legitimate "matches nothing" result, not an error."""
    lbs_r = storage.lb_list(src_id)
    if isinstance(lbs_r, Err):
        return lbs_r
    lb = next((l for l in lbs_r.value if l.name == lb_name), None)
    if lb is None:
        return Err(NotFound(entity="Label", key=lb_name))

    txns_r = storage.txn_query(src_id=src_id, lb_ids=[lb.lb_id], include_archive=True)
    if isinstance(txns_r, Err):
        return txns_r
    folded = fold_source(txns_r.value)  # {(lb_id, id_id): val_id}

    matching: List[IdId] = []
    val_cache = {}
    for (_, id_id), val_id in folded.items():
        if val_id == 0:  # DELETE -- no string value to compare
            continue
        if val_id not in val_cache:
            vr = storage.val_get(ValId(val_id))
            if isinstance(vr, Err):
                return vr
            val_cache[val_id] = vr.value
        if val_cache[val_id] == target:
            matching.append(IdId(id_id))
    return Ok(sorted(matching))


def resolve_selector(
    storage: StoragePort,
    *,
    src_name: str,
    lb_names: Optional[List[str]] = None,
    id_values: Optional[List[str]] = None,
    where: Optional[Tuple[str, str]] = None,
    cnts: Optional[List[int]] = None,
    from_dt: Optional[float] = None,
    until_dt: Optional[float] = None,
    created_from: Optional[float] = None,
    created_until: Optional[float] = None,
) -> Union[Ok[Selector], _Err]:
    """Resolve CLI-facing names/values to a Selector, side-effect free (like
    `ds get`'s own resolution): an unknown source/label/id is NotFound, never
    a silently-created pool entry. `cnts` is a standalone selector mode --
    when given, lb_names/id_values/where/date ranges are ignored (the CLI
    itself keeps them mutually exclusive; this function just doesn't need
    them to build a --cnt Selector)."""
    src_r = resolve_src(storage, src_name)
    if isinstance(src_r, Err):
        return src_r
    src_id = SrcId(src_r.value.src_id)

    if cnts is not None:
        cnt_ids = [CntId(c) for c in cnts]
        found_r = storage.txn_query(src_id=src_id, cnts=cnt_ids, include_archive=True)
        if isinstance(found_r, Err):
            return found_r
        found = {int(t.cnt) for t in found_r.value}
        missing = [c for c in cnts if c not in found]
        if missing:
            return Err(NotFound(entity="Transaction", key=f"cnt {missing[0]} in source {src_name}"))
        return Ok(Selector(src_id=src_id, cnts=cnt_ids))

    lb_ids: Optional[List[LbId]] = None
    if lb_names:
        lb_ids_r = resolve_lb_ids(storage, src_id, lb_names)
        if isinstance(lb_ids_r, Err):
            return lb_ids_r
        lb_ids = lb_ids_r.value

    id_ids: Optional[List[IdId]] = None
    if where is not None:
        id_ids_r = _resolve_where(storage, src_id, where[0], where[1])
        if isinstance(id_ids_r, Err):
            return id_ids_r
        id_ids = id_ids_r.value
    elif id_values:
        id_ids_r = resolve_id_ids(storage, id_values)
        if isinstance(id_ids_r, Err):
            return id_ids_r
        id_ids = id_ids_r.value

    return Ok(Selector(
        src_id=src_id, lb_ids=lb_ids, id_ids=id_ids,
        from_dt=from_dt, until_dt=until_dt,
        created_from=created_from, created_until=created_until,
    ))


def count_matching(storage: StoragePort, selector: Selector) -> Union[Ok[int], Err[StorageError]]:
    """How many transactions (active + archived) `selector` matches -- used
    to show a confirmation preview before the irreversible/semi-irreversible op."""
    txns_r = storage.txn_query(
        src_id=selector.src_id, lb_ids=selector.lb_ids, id_ids=selector.id_ids,
        cnts=selector.cnts, from_dt=selector.from_dt, until_dt=selector.until_dt,
        created_from=selector.created_from, created_until=selector.created_until,
        include_archive=True,
    )
    if isinstance(txns_r, Err):
        return txns_r
    return Ok(len(txns_r.value))
