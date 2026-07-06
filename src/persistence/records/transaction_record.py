from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class TransactionRecord:
    cnt: int
    act: int
    dt: float
    src: int
    lb: int
    id: int
    p: float
    val: int = 0  # 0 = no value (DELETE semantics); val_id is AUTOINCREMENT from 1

    @staticmethod
    def from_row(row: Tuple) -> TransactionRecord:
        return TransactionRecord(
            cnt=row[0],
            act=row[1],
            dt=row[2],
            src=row[3],
            lb=row[4],
            id=row[5],
            val=row[6] or 0,  # NULL from SQLite → 0 (DELETE sentinel)
            p=row[7],
        )
