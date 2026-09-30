from __future__ import annotations

import json
from pathlib import Path

from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import StorageError
from src.domain.result import Err, Ok

_VALID_TYPES = ("text", "number", "date", "bool")


def _load_label_spec(entry: object) -> Ok[LabelConfig] | Err[StorageError]:
    if not isinstance(entry, dict):
        return Err(StorageError(f"each item in 'labels' must be an object, got {entry!r}"))
    try:
        name = entry["name"]
    except KeyError:
        return Err(StorageError(f"label missing required field 'name': {entry!r}"))

    type_ = entry.get("type", "text")
    if type_ not in _VALID_TYPES:
        return Err(StorageError(
            f"label '{name}': invalid type {type_!r} (must be one of {_VALID_TYPES})"
        ))

    try:
        return Ok(LabelConfig(
            name=name,
            type=type_,
            archive=bool(entry.get("archive", False)),
            publish=bool(entry.get("publish", True)),
            p=float(entry.get("p", 0.5)),
            description=entry.get("description"),
        ))
    except (TypeError, ValueError) as exc:
        return Err(StorageError(f"label '{name}': {exc}"))


def load_source(source_dir: Path) -> Ok[SourceConfig] | Err[StorageError]:
    try:
        data = json.loads((source_dir / "source.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return Err(StorageError(str(exc)))

    raw_labels = data.get("labels", [])
    if not isinstance(raw_labels, list):
        return Err(StorageError("'labels' must be an array"))

    labels: dict[str, LabelConfig] = {}
    for entry in raw_labels:
        result = _load_label_spec(entry)
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
