from __future__ import annotations

from dataclasses import dataclass
from typing import NewType, Optional  # Optional kept for Src/Lb metadata fields only

# --- Integer keys into pool tables ---
SrcId = NewType("SrcId", int)   # srcs.src_id
LbId  = NewType("LbId",  int)   # lbs.lb_id
IdId  = NewType("IdId",  int)   # ids.id_id
ValId = NewType("ValId", int)   # vals.val_id
ActId = NewType("ActId", int)   # acts.act_id
CntId = NewType("CntId", int)   # cnts.cnt_id


@dataclass(frozen=True)
class Src:
    src_id: SrcId
    name: str
    p: float
    key_label: Optional[LbId]  # None until the key label is bootstrapped (see StoragePort.src_set_key_label)
    description: Optional[str] = None
    # Bumped by txn_delete/txn_archive/txn_unarchive/lb_merge (never by txn_insert/load) --
    # lets `ds get --cache` tell "pure appends since last time" from "something
    # structural happened" without re-diffing the whole fold. See
    # docs/decisions/0010-incremental-fold-cache.md.
    struct_version: int = 0


@dataclass(frozen=True)
class Lb:
    lb_id: LbId
    name: str
    p: float
    src: SrcId  # labels are source-specific: same name in two sources is not the same label
    description: Optional[str] = None


@dataclass(frozen=True)
class TransactionInput:
    """Fields supplied by the caller when inserting a new transaction.
    The storage layer generates cnt and created_at internally."""
    act: ActId
    dt: float
    src: SrcId
    lb: LbId
    id: IdId
    p: float
    val: ValId = ValId(0)  # 0 = DELETE semantics; val_id is AUTOINCREMENT from 1


@dataclass(frozen=True)
class Transaction:
    """Full transaction record as stored in DB (cnt and created_at are assigned by storage)."""
    cnt: CntId
    act: ActId
    dt: float
    src: SrcId
    lb: LbId
    id: IdId
    p: float
    created_at: float  # when the record was physically inserted (distinct from dt, the business timestamp)
    val: ValId = ValId(0)  # 0 = DELETE semantics
