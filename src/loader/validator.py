from __future__ import annotations

from src.config.models import SourceConfig
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok


def validate_table(data: dict, cfg: SourceConfig) -> Ok[dict] | Err[ValidationError]:
    if not isinstance(data, dict):
        return Err(ValidationError(field="data", message="must be a JSON object"))

    for col, vals in data.items():
        if not isinstance(vals, list):
            return Err(ValidationError(field=col, message="column values must be a list"))

    if cfg.key_label not in data:
        return Err(ValidationError(
            field=cfg.key_label,
            message=f"key_label column '{cfg.key_label}' not found in data",
        ))

    lengths = {col: len(vals) for col, vals in data.items()}
    if len(set(lengths.values())) > 1:
        return Err(ValidationError(
            field="columns",
            message=f"all columns must have the same length: {lengths}",
        ))

    for val in data[cfg.key_label]:
        if val is None:
            return Err(ValidationError(
                field=cfg.key_label,
                message="key_label column must not contain null values",
            ))

    key_strs = [str(v) for v in data[cfg.key_label]]
    if len(key_strs) != len(set(key_strs)):
        return Err(ValidationError(
            field=cfg.key_label,
            message="key_label column contains duplicate values",
        ))

    return Ok(data)
