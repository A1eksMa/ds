from __future__ import annotations

from typing import Union

from src.domain.entities import Lb, LbId, Src, SrcId
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok
from src.persistence.records.src_record import SrcRecord


def record_to_domain(record: SrcRecord) -> Union[Ok[Src], Err[ValidationError]]:
    if record.p < 0.0 or record.p > 1.0:
        return Err(ValidationError(field="p", message="must be between 0.0 and 1.0"))
    return Ok(Src(
        src_id=SrcId(record.src_id),
        name=record.name,
        p=record.p,
        key_label=LbId(record.key_label) if record.key_label is not None else None,
        description=record.description,
        struct_version=record.struct_version,
    ))


def domain_to_record(src: Src) -> SrcRecord:
    return SrcRecord(
        src_id=int(src.src_id),
        name=src.name,
        p=src.p,
        key_label=int(src.key_label) if src.key_label is not None else None,
        description=src.description,
        struct_version=src.struct_version,
    )
