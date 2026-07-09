from __future__ import annotations

from typing import Dict, Iterable, Tuple

from src.domain.entities import IdId, LbId, SrcId, Transaction, ValId

StateKey = Tuple[SrcId, LbId, IdId]
State = Dict[StateKey, ValId]


def fold_state(transactions: Iterable[Transaction]) -> State:
    """Level 1 (single source) collision resolution.

    Folds a transaction log into the latest value per (src, lb, id) key:
    later transactions (by cnt, the storage-assigned insertion order)
    overwrite earlier ones for the same key -- the "more recent data wins"
    rule from docs/proposals/DATABASE_DESIGN.md. Input order is not assumed;
    transactions are sorted by cnt before folding.

    val == ValId(0) marks a DELETE and is kept as a state entry rather than
    dropped, so callers can tell "deleted" apart from "never existed".
    """
    state: State = {}
    for txn in sorted(transactions, key=lambda t: int(t.cnt)):
        state[(txn.src, txn.lb, txn.id)] = txn.val
    return state
