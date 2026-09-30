from __future__ import annotations

from typing import NamedTuple, Optional, Union

from src.domain.entities import LbId, SrcId
from src.domain.errors import NotFound, StorageError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort

_Err = Union[Err[StorageError], Err[NotFound]]


class Target(NamedTuple):
    """Resolved --src/--lb pair, ready for txn_delete / a matching-count preview."""
    src_id: SrcId
    lb_id: Optional[LbId]


def resolve_target(
    storage: StoragePort, src_name: str, lb_name: Optional[str] = None,
) -> Union[Ok[Target], _Err]:
    """Resolve --src/--lb names to ids, side-effect free (mirrors `ds get`'s
    resolution in service/get.py::run_get / build_source): an unknown name is
    a NotFound error, never a silently-created pool entry."""
    srcs_r = storage.src_list()
    if isinstance(srcs_r, Err):
        return srcs_r
    src = next((s for s in srcs_r.value if s.name == src_name), None)
    if src is None:
        return Err(NotFound(entity="Source", key=src_name))

    if lb_name is None:
        return Ok(Target(SrcId(src.src_id), None))

    lbs_r = storage.lb_list(SrcId(src.src_id))
    if isinstance(lbs_r, Err):
        return lbs_r
    lb = next((l for l in lbs_r.value if l.name == lb_name), None)
    if lb is None:
        return Err(NotFound(entity="Label", key=f"{src_name}.{lb_name}"))
    return Ok(Target(SrcId(src.src_id), LbId(lb.lb_id)))


def count_matching(
    storage: StoragePort, target: Target,
) -> Union[Ok[int], Err[StorageError]]:
    """How many transactions (active + archived) a delete of `target` would
    remove — used to show a confirmation preview before the irreversible op."""
    txns_r = storage.txn_query(
        src_id=target.src_id, lb_id=target.lb_id, include_archive=True,
    )
    if isinstance(txns_r, Err):
        return txns_r
    return Ok(len(txns_r.value))
