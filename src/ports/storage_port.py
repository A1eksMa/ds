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

    def lb_intern(self, name: str, src_id: SrcId) -> Union[Ok[LbId], Err[StorageError]]: ...

    def id_intern(self, value: str) -> Union[Ok[IdId], Err[StorageError]]: ...

    def id_get(self, id_id: IdId) -> Union[Ok[str], Err[StorageError]]: ...

    # Batched id_get: one round trip (chunked) instead of one per id_id --
    # what `ds get` uses to resolve a whole source's rows (see
    # src/service/get.py::_build_source). A ValId/IdId absent from the DB is
    # simply absent from the returned mapping (same "missing -> absent"
    # convention as txn_last_values), not an error.
    def id_get_many(self, id_ids: List[IdId]) -> Union[Ok[Dict[int, str]], Err[StorageError]]: ...

    # Reverse lookup, side-effect free (unlike id_intern -- doesn't create a
    # pool entry for an unknown value). None = the value was never interned.
    def id_lookup(self, value: str) -> Union[Ok[Optional[IdId]], Err[StorageError]]: ...

    def val_intern(self, value: str) -> Union[Ok[ValId], Err[StorageError]]: ...

    def val_get(self, val_id: ValId) -> Union[Ok[str], Err[StorageError]]: ...

    # Batched val_get -- see id_get_many.
    def val_get_many(self, val_ids: List[ValId]) -> Union[Ok[Dict[int, str]], Err[StorageError]]: ...

    def act_intern(self, act: Act) -> Union[Ok[ActId], Err[StorageError]]: ...

    # --- Source metadata ---
    # Every Src carries struct_version, an opaque-to-callers counter bumped by
    # txn_delete/txn_archive/txn_unarchive/lb_merge (never by txn_insert) --
    # how `ds get --cache` tells "pure appends since last time" from
    # "something structural happened" (see docs/decisions/0010-incremental-fold-cache.md).

    def src_get_or_create(
        self, name: str
    ) -> Union[Ok[Src], Err[StorageError]]: ...

    def src_get(self, src_id: SrcId) -> Union[Ok[Src], Err[StorageError]]: ...

    def src_update(self, src: Src) -> Union[Ok[None], Err[StorageError]]: ...

    def src_list(self) -> Union[Ok[List[Src]], Err[StorageError]]: ...

    # Bootstraps Src.key_label once the key label's Lb row exists (see the
    # Src/Lb creation-order note on lb_intern: a source's key label cannot be
    # interned until its src_id exists, so key_label starts out None).
    def src_set_key_label(
        self, src_id: SrcId, lb_id: LbId
    ) -> Union[Ok[None], Err[StorageError]]: ...

    # --- Label metadata ---

    def lb_get(self, lb_id: LbId) -> Union[Ok[Lb], Err[StorageError]]: ...

    def lb_update(self, lb: Lb) -> Union[Ok[None], Err[StorageError]]: ...

    def lb_list(self, src_id: Optional[SrcId] = None) -> Union[Ok[List[Lb]], Err[StorageError]]: ...

    # `ds mv`: repoints every transaction (active + archived) referencing
    # from_lb_id onto into_lb_id -- both its lb and src columns, since
    # into_lb_id may belong to a different source than from_lb_id did -- then
    # deletes the now-orphaned from_lb_id row from lbs (nothing references it
    # anymore, so this never trips the lbs FK's ON DELETE RESTRICT). Returns
    # the number of transactions moved. Caller resolves/creates into_lb_id
    # first (see src/service/mv.py) -- this primitive assumes it already
    # exists and never creates a pool entry itself.
    def lb_merge(
        self, from_lb_id: LbId, into_lb_id: LbId,
    ) -> Union[Ok[int], Err[StorageError]]: ...

    # --- Transactions ---

    def txn_insert(
        self, txn: TransactionInput, archived: bool = False,
    ) -> Union[Ok[Transaction], Err[StorageError]]: ...

    # lb_ids/id_ids/cnts: None = no filter on that dimension; an explicitly
    # empty list means "matches nothing" (e.g. a --where condition in
    # src/service/selector.py that resolved to zero keys). from_dt/until_dt
    # filter on business time (dt); created_from/created_until on physical
    # load time (created_at) -- the same two axes selector.py exposes as
    # --dt-from/--dt-until and --created-from/--created-until.
    def txn_query(
        self,
        src_id: Optional[SrcId] = None,
        lb_ids: Optional[List[LbId]] = None,
        id_ids: Optional[List[IdId]] = None,
        cnts: Optional[List[CntId]] = None,
        from_dt: Optional[float] = None,
        until_dt: Optional[float] = None,
        created_from: Optional[float] = None,
        created_until: Optional[float] = None,
        from_cnt: Optional[CntId] = None,
        include_archive: bool = False,
    ) -> Union[Ok[List[Transaction]], Err[StorageError]]: ...

    # Same filter set as txn_query (minus from_cnt/include_archive, which
    # don't apply to a write): moves matching active transactions into
    # transactions_archive. No filters at all -> archives everything (the
    # CLI, not the port, is what requires --src -- see src/cli/commands.py).
    def txn_archive(
        self,
        src_id: Optional[SrcId] = None,
        lb_ids: Optional[List[LbId]] = None,
        id_ids: Optional[List[IdId]] = None,
        cnts: Optional[List[CntId]] = None,
        from_dt: Optional[float] = None,
        until_dt: Optional[float] = None,
        created_from: Optional[float] = None,
        created_until: Optional[float] = None,
    ) -> Union[Ok[int], Err[StorageError]]: ...

    # Mirror of txn_archive: moves matching transactions from transactions_archive
    # back into transactions. Same filter set, same "no filters -> everything" rule.
    def txn_unarchive(
        self,
        src_id: Optional[SrcId] = None,
        lb_ids: Optional[List[LbId]] = None,
        id_ids: Optional[List[IdId]] = None,
        cnts: Optional[List[CntId]] = None,
        from_dt: Optional[float] = None,
        until_dt: Optional[float] = None,
        created_from: Optional[float] = None,
        created_until: Optional[float] = None,
    ) -> Union[Ok[int], Err[StorageError]]: ...

    # Same filter set again: physically removes matching transactions from
    # BOTH transactions and transactions_archive; returns the total removed
    # across both tables.
    def txn_delete(
        self,
        src_id: Optional[SrcId] = None,
        lb_ids: Optional[List[LbId]] = None,
        id_ids: Optional[List[IdId]] = None,
        cnts: Optional[List[CntId]] = None,
        from_dt: Optional[float] = None,
        until_dt: Optional[float] = None,
        created_from: Optional[float] = None,
        created_until: Optional[float] = None,
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

