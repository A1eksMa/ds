from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import StorageError
from src.domain.result import Err, Ok


def _label_to_dict(lb: LabelConfig) -> dict:
    # only write fields that differ from the default -- keeps a hand-editable,
    # low-noise file (see docs/reference/config-format.md)
    d: dict = {"name": lb.name}
    if lb.type != "text":
        d["type"] = lb.type
    if lb.archive:
        d["archive"] = True
    if lb.publish:
        d["publish"] = True
    if lb.p != 0.5:
        d["p"] = lb.p
    if lb.description is not None:
        d["description"] = lb.description
    return d


def write_source(path: Path, cfg: SourceConfig) -> Union[Ok[None], Err[StorageError]]:
    """Serialize cfg back to source.json, in the same shape load_source()
    reads (see src/config/loader.py). Omits fields at their default value."""
    doc: dict = {"name": cfg.name, "key_label": cfg.key_label}
    if cfg.p != 0.5:
        doc["p"] = cfg.p
    if cfg.description is not None:
        doc["description"] = cfg.description
    if cfg.labels:
        # stable, human-friendly order: key_label first (if declared), then alphabetical
        names = sorted(cfg.labels, key=lambda n: (n != cfg.key_label, n))
        doc["labels"] = [_label_to_dict(cfg.labels[n]) for n in names]

    try:
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return Ok(None)
    except OSError as exc:
        return Err(StorageError(str(exc)))
