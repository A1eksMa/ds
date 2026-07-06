from __future__ import annotations

import json
from pathlib import Path

from src.config.models import SourceConfig
from src.domain.enums import Act
from src.domain.errors import StorageError, ValidationError
from src.domain.result import Err, Ok
from src.loader import json_loader
from src.ports.storage_port import StoragePort


def load(
    storage: StoragePort,
    data: dict,
    cfg: SourceConfig,
    dt: float,
    act: Act = Act.POST,
) -> Ok[int] | Err[StorageError] | Err[ValidationError]:
    return json_loader.load(storage, data, cfg, dt, act)


def load_file(
    storage: StoragePort,
    path: Path,
    cfg: SourceConfig,
    dt: float,
    act: Act = Act.POST,
) -> Ok[int] | Err[StorageError] | Err[ValidationError]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Err(StorageError(str(exc)))
    return load(storage, data, cfg, dt, act)
