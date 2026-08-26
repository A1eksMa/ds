from __future__ import annotations

from typing import Union

from src.domain.entities import Lb, LbId, SrcId
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok
from src.persistence.records.lb_record import LbRecord


def record_to_domain(record: LbRecord) -> Union[Ok[Lb], Err[ValidationError]]:
    if record.p < 0.0 or record.p > 1.0:
        return Err(ValidationError(field="p", message="must be between 0.0 and 1.0"))
    return Ok(Lb(
        lb_id=LbId(record.lb_id),
        name=record.name,
        p=record.p,
        src=SrcId(record.src),
        description=record.description,
    ))


def domain_to_record(lb: Lb) -> LbRecord:
    return LbRecord(
        lb_id=int(lb.lb_id),
        name=lb.name,
        p=lb.p,
        src=int(lb.src),
        description=lb.description,
    )
