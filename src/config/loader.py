from __future__ import annotations

import json
from pathlib import Path

from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import StorageError
from src.domain.result import Err, Ok


def _load_label(path: Path) -> Ok[LabelConfig] | Err[StorageError]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Ok(LabelConfig(
            name=data["name"],
            p=float(data.get("p", 0.5)),
            description=data.get("description"),
        ))
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return Err(StorageError(str(exc)))


def load_source(source_dir: Path) -> Ok[SourceConfig] | Err[StorageError]:
    try:
        data = json.loads((source_dir / "source.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return Err(StorageError(str(exc)))

    labels: dict[str, LabelConfig] = {}
    labels_dir = source_dir / "labels"
    if labels_dir.exists():
        for label_dir in sorted(labels_dir.iterdir()):
            if not label_dir.is_dir():
                continue
            config_file = label_dir / "config.json"
            if not config_file.exists():
                continue
            result = _load_label(config_file)
            if isinstance(result, Err):
                return result
            labels[result.value.name] = result.value

    try:
        return Ok(SourceConfig(
            name=data["name"],
            key_label=data["key_label"],
            p=float(data.get("p", 0.5)),
            description=data.get("description"),
            labels=labels,
        ))
    except KeyError as exc:
        return Err(StorageError(f"missing required field: {exc}"))
