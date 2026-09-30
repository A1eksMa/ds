from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from src.domain.entities import CntId, IdId, LbId, SrcId
from src.domain.errors import StorageError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort


@dataclass(frozen=True)
class DuplicateRecord:
    """A transaction that repeats the value already in effect right before it,
    for the same (lb, id) -- removing it changes no `ds get` fold at any
    as-of date (see docs/reference/cli.md#ds-compact). `active` says whether
    it's currently in `transactions` (vs already sitting in
    transactions_archive) -- soft compaction only ever touches active ones."""
    cnt: CntId
    lb_id: LbId
    id_id: IdId
    dt: float
    val: int
    active: bool


def find_duplicates(
    storage: StoragePort,
    src_id: SrcId,
    lb_ids: Optional[List[LbId]] = None,
    id_ids: Optional[List[IdId]] = None,
    from_dt: Optional[float] = None,
    until_dt: Optional[float] = None,
) -> Union[Ok[List[DuplicateRecord]], Err[StorageError]]:
    """Scan the (optionally date-windowed) history of every (lb, id) pair in
    scope, oldest-first (active + archived together), and flag every
    transaction whose value repeats the one already in effect right before
    it. The first transaction found within the window is always the anchor
    and is never flagged -- even if it would itself duplicate something
    earlier that fell outside the window; a caller-given date range
    deliberately excludes everything before/after it from consideration, not
    just from removal."""
    full_r = storage.txn_query(
        src_id=src_id, lb_ids=lb_ids, id_ids=id_ids,
        from_dt=from_dt, until_dt=until_dt, include_archive=True,
    )
    if isinstance(full_r, Err):
        return full_r
    active_r = storage.txn_query(
        src_id=src_id, lb_ids=lb_ids, id_ids=id_ids,
        from_dt=from_dt, until_dt=until_dt, include_archive=False,
    )
    if isinstance(active_r, Err):
        return active_r
    active_cnts = {int(t.cnt) for t in active_r.value}

    groups: Dict[Tuple[int, int], List] = {}
    for t in full_r.value:
        groups.setdefault((int(t.lb), int(t.id)), []).append(t)

    duplicates: List[DuplicateRecord] = []
    for (lb, id_), txns in groups.items():
        ordered = sorted(txns, key=lambda t: (t.dt, int(t.cnt)))
        last_val: Optional[int] = None
        for i, t in enumerate(ordered):
            v = int(t.val)
            if i == 0:
                last_val = v
                continue
            if v == last_val:
                duplicates.append(DuplicateRecord(
                    cnt=t.cnt, lb_id=LbId(lb), id_id=IdId(id_),
                    dt=t.dt, val=v, active=int(t.cnt) in active_cnts,
                ))
            else:
                last_val = v

    duplicates.sort(key=lambda d: int(d.cnt))
    return Ok(duplicates)
