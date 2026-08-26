from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class LbRecord:
    lb_id: int
    name: str
    p: float
    src: int
    description: Optional[str] = None

    @staticmethod
    def from_row(row: Tuple) -> LbRecord:
        return LbRecord(
            lb_id=row[0],
            name=row[1],
            description=row[2],
            p=row[3],
            src=row[4],
        )
