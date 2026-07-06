from __future__ import annotations

from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok


def validate_label(cfg: LabelConfig) -> Ok[LabelConfig] | Err[ValidationError]:
    if not (0.0 <= cfg.p <= 1.0):
        return Err(ValidationError(field="p", message=f"must be between 0.0 and 1.0, got {cfg.p}"))
    return Ok(cfg)


def validate_source(cfg: SourceConfig) -> Ok[SourceConfig] | Err[ValidationError]:
    if not (0.0 <= cfg.p <= 1.0):
        return Err(ValidationError(field="p", message=f"must be between 0.0 and 1.0, got {cfg.p}"))
    if cfg.key_label not in cfg.labels:
        return Err(ValidationError(
            field="key_label",
            message=f"'{cfg.key_label}' not found in labels",
        ))
    for name, label in cfg.labels.items():
        result = validate_label(label)
        if isinstance(result, Err):
            return Err(ValidationError(
                field=f"labels.{name}.p",
                message=result.error.message,
            ))
    return Ok(cfg)
