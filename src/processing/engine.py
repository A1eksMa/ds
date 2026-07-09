from __future__ import annotations

from typing import Optional, Union

from src.domain.entities import IdId, LbId, SrcId
from src.domain.errors import StorageError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort
from src.processing.single_source import State, fold_state


def build_state(
    storage: StoragePort,
    src_id: Optional[SrcId] = None,
    lb_id: Optional[LbId] = None,
    id_id: Optional[IdId] = None,
    until_dt: Optional[float] = None,
    include_archive: bool = False,
) -> Union[Ok[State], Err[StorageError]]:
    """Build the Level 1 state snapshot: the latest val per (src, lb, id) as
    of until_dt (or now, if omitted), read from the transaction log.

    Cross-source, weight-based collision resolution (Level 2 / Multi Source)
    is not applied here -- each (src, lb, id) key keeps its own value
    independently of any other source.
    """
    result = storage.txn_query(
        src_id=src_id,
        lb_id=lb_id,
        id_id=id_id,
        until_dt=until_dt,
        include_archive=include_archive,
    )
    if isinstance(result, Err):
        return result
    return Ok(fold_state(result.value))
