from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Union

from src.config.models import SourceConfig
from src.domain.errors import StorageError, ValidationError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort

_Err = Union[Err[ValidationError], Err[StorageError]]

_BOOL_TRUE = {"true", "1", "yes", "y"}
_BOOL_FALSE = {"false", "0", "no", "n"}
_TS_RE = re.compile(r"\d{9,13}")


def _is_valid_number(raw: str) -> bool:
    try:
        float(raw)
        return True
    except ValueError:
        return False


def _is_valid_date(raw: str) -> bool:
    s = raw.strip()
    try:
        datetime.fromisoformat(s)
        return True
    except ValueError:
        pass
    return bool(_TS_RE.fullmatch(s))  # unix timestamp, seconds or milliseconds


def _is_valid_bool(raw: str) -> bool:
    s = raw.strip().lower()
    return s in _BOOL_TRUE or s in _BOOL_FALSE


def _is_valid_for_type(raw: object, type_: str) -> bool:
    if raw is None:
        return True  # DELETE marker -- valid regardless of declared type
    s = str(raw)
    if type_ == "number":
        return _is_valid_number(s)
    if type_ == "date":
        return _is_valid_date(s)
    if type_ == "bool":
        return _is_valid_bool(s)
    return True  # "text" (or a label with no declared type) -- no constraint


def validate_known_schema(
    storage: StoragePort, data: dict, cfg: SourceConfig,
) -> Union[Ok[None], _Err]:
    """`ds upload`'s stricter gate on top of validate_table(): every column
    (besides key_label) must already be known for this source -- either
    already loaded before (present in the DB's lbs pool for it) or declared
    in source.json's labels[] -- and every non-null value must parse under
    its declared type. A label known only from the DB (never declared in
    source.json) has no type on record and defaults to "text" -- no
    constraint. Reports the first problem found; the caller loads nothing at
    all if this returns Err (see src/cli/commands.py::_upload)."""
    known_types: Dict[str, str] = {}

    srcs_r = storage.src_list()
    if isinstance(srcs_r, Err):
        return srcs_r
    src = next((s for s in srcs_r.value if s.name == cfg.name), None)
    if src is not None:
        lbs_r = storage.lb_list(src.src_id)
        if isinstance(lbs_r, Err):
            return lbs_r
        for lb in lbs_r.value:
            known_types[lb.name] = "text"  # ds doesn't persist type in the DB

    for name, label_cfg in cfg.labels.items():
        known_types[name] = label_cfg.type  # source.json's declared type wins

    for col, values in data.items():
        if col == cfg.key_label:
            continue
        if col not in known_types:
            return Err(ValidationError(
                field=col,
                message=f"unknown label '{col}' -- not previously loaded for '{cfg.name}' "
                        f"and not declared in its source.json",
            ))
        type_ = known_types[col]
        for i, raw in enumerate(values):
            if not _is_valid_for_type(raw, type_):
                return Err(ValidationError(
                    field=col,
                    message=f"value {raw!r} at row {i} does not parse as declared type {type_!r}",
                ))

    return Ok(None)
