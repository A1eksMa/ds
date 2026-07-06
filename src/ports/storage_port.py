from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union
from typing import Protocol, runtime_checkable

from src.domain.entities import (
    ActId, CntId, IdId, LbId, SrcId, ValId,
    Lb, Src, Transaction, TransactionInput,
)
from src.domain.enums import Act
from src.domain.errors import StorageError
from src.domain.result import Err, Ok


@runtime_checkable
class StoragePort(Protocol):
    # --- Transaction control ---
    def begin(self) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...

    # --- String pool operations ---
    # Intern a string into the corresponding pool table; return its integer ID.
    # Creates the entry if it does not exist yet.

    def lb_intern(self, name: str) -> Union[Ok[LbId], Err[StorageError]]: ...

    def id_intern(self, value: str) -> Union[Ok[IdId], Err[StorageError]]: ...

    def id_get(self, id_id: IdId) -> Union[Ok[str], Err[StorageError]]: ...

    def val_intern(self, value: str) -> Union[Ok[ValId], Err[StorageError]]: ...

    def val_get(self, val_id: ValId) -> Union[Ok[str], Err[StorageError]]: ...

    def act_intern(self, act: Act) -> Union[Ok[ActId], Err[StorageError]]: ...

    # --- Source metadata ---

    def src_get_or_create(
        self, name: str, key_label_id: LbId
    ) -> Union[Ok[Src], Err[StorageError]]: ...

    def src_get(self, src_id: SrcId) -> Union[Ok[Src], Err[StorageError]]: ...

    def src_update(self, src: Src) -> Union[Ok[None], Err[StorageError]]: ...

    def src_list(self) -> Union[Ok[List[Src]], Err[StorageError]]: ...

    # --- Label metadata ---

    def lb_get(self, lb_id: LbId) -> Union[Ok[Lb], Err[StorageError]]: ...

    def lb_update(self, lb: Lb) -> Union[Ok[None], Err[StorageError]]: ...

    def lb_list(self) -> Union[Ok[List[Lb]], Err[StorageError]]: ...

    # --- Transactions ---

    def txn_insert(
        self, txn: TransactionInput
    ) -> Union[Ok[Transaction], Err[StorageError]]: ...

    def txn_query(
        self,
        src_id: Optional[SrcId] = None,
        lb_id: Optional[LbId] = None,
        id_id: Optional[IdId] = None,
        until_dt: Optional[float] = None,
        from_cnt: Optional[CntId] = None,
        include_archive: bool = False,
    ) -> Union[Ok[List[Transaction]], Err[StorageError]]: ...

    def txn_archive(self, until_dt: float) -> Union[Ok[int], Err[StorageError]]: ...

    def txn_delete(
        self,
        src_id: SrcId,
        lb_id: Optional[LbId] = None,
    ) -> Union[Ok[int], Err[StorageError]]: ...

    # --- Bulk history lookup (for act auto-detection on load) ---
    # For each (lb, id) pair in lb_ids x id_ids that has at least one
    # transaction (active or archived) under src_id, return its most
    # recent val (by cnt). Pairs with no history are simply absent from
    # the returned mapping — callers should treat a missing key the same
    # as val=0 (no prior value == PATCH territory).

    def txn_last_values(
        self,
        src_id: SrcId,
        lb_ids: List[LbId],
        id_ids: List[IdId],
    ) -> Union[Ok[Dict[Tuple[LbId, IdId], ValId]], Err[StorageError]]: ...

