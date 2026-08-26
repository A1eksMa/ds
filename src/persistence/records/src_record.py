from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class SrcRecord:
    src_id: int
    name: str
    p: float
    key_label: Optional[int]  # None until bootstrapped
    description: Optional[str] = None

    @staticmethod
    def from_row(row: Tuple) -> SrcRecord:
        return SrcRecord(
            src_id=row[0],
            name=row[1],
            description=row[2],
            p=row[3],
            key_label=row[4],
        )
