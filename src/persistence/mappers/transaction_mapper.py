from __future__ import annotations

from typing import Union

from src.domain.entities import (
    ActId, CntId, IdId, LbId, SrcId, ValId,
    Transaction, TransactionInput,
)
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok
from src.persistence.records.transaction_record import TransactionRecord


def record_to_domain(record: TransactionRecord) -> Union[Ok[Transaction], Err[ValidationError]]:
    if record.p < 0.0 or record.p > 1.0:
        return Err(ValidationError(field="p", message="must be between 0.0 and 1.0"))
    return Ok(Transaction(
        cnt=CntId(record.cnt),
        act=ActId(record.act),
        dt=record.dt,
        src=SrcId(record.src),
        lb=LbId(record.lb),
        id=IdId(record.id),
        p=record.p,
        created_at=record.created_at,
        val=ValId(record.val),
    ))


def domain_to_record(txn: Transaction) -> TransactionRecord:
    return TransactionRecord(
        cnt=int(txn.cnt),
        act=int(txn.act),
        dt=txn.dt,
        src=int(txn.src),
        lb=int(txn.lb),
        id=int(txn.id),
        p=txn.p,
        created_at=txn.created_at,
        val=int(txn.val),
    )


def input_to_row(txn: TransactionInput, cnt: CntId, created_at: float) -> TransactionRecord:
    return TransactionRecord(
        cnt=int(cnt),
        act=int(txn.act),
        dt=txn.dt,
        src=int(txn.src),
        lb=int(txn.lb),
        id=int(txn.id),
        p=txn.p,
        created_at=created_at,
        val=int(txn.val),
    )
