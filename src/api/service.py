from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.config.models import SourceConfig
from src.domain.entities import LbId, SrcId
from src.domain.errors import NotFound, StorageError, ValidationError
from src.domain.result import Err, Ok
from src.loader import json_loader
from src.ports.storage_port import StoragePort
from src.processing.engine import build_state
from src.processing.single_source import State


def load(
    storage: StoragePort,
    data: dict,
    cfg: SourceConfig,
    dt: float,
) -> Ok[int] | Err[StorageError] | Err[ValidationError]:
    return json_loader.load(storage, data, cfg, dt)


def load_file(
    storage: StoragePort,
    path: Path,
    cfg: SourceConfig,
    dt: float,
) -> Ok[int] | Err[StorageError] | Err[ValidationError]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Err(StorageError(str(exc)))
    return load(storage, data, cfg, dt)


def _find_src(storage: StoragePort, name: str) -> Ok[SrcId] | Err[StorageError] | Err[NotFound]:
    listed = storage.src_list()
    if isinstance(listed, Err):
        return listed
    for src in listed.value:
        if src.name == name:
            return Ok(src.src_id)
    return Err(NotFound(entity="Src", key=name))


def _find_lb(storage: StoragePort, name: str) -> Ok[LbId] | Err[StorageError] | Err[NotFound]:
    listed = storage.lb_list()
    if isinstance(listed, Err):
        return listed
    for lb in listed.value:
        if lb.name == name:
            return Ok(lb.lb_id)
    return Err(NotFound(entity="Lb", key=name))


def _state_to_records(
    storage: StoragePort, state: State
) -> Ok[List[dict]] | Err[StorageError]:
    """Resolve a raw {(src, lb, id): val} state (interned int ids) into
    human-readable records, sorted by key for deterministic output."""
    src_names: Dict[SrcId, str] = {}
    lb_names: Dict[LbId, str] = {}
    records: List[dict] = []
    for (src_id, lb_id, id_id), val_id in sorted(state.items()):
        if src_id not in src_names:
            r = storage.src_get(src_id)
            if isinstance(r, Err):
                return r
            src_names[src_id] = r.value.name
        if lb_id not in lb_names:
            r = storage.lb_get(lb_id)
            if isinstance(r, Err):
                return r
            lb_names[lb_id] = r.value.name
        id_r = storage.id_get(id_id)
        if isinstance(id_r, Err):
            return id_r
        val_value: Optional[str] = None
        if int(val_id) != 0:
            val_r = storage.val_get(val_id)
            if isinstance(val_r, Err):
                return val_r
            val_value = val_r.value
        records.append({
            "src": src_names[src_id],
            "lb": lb_names[lb_id],
            "id": id_r.value,
            "val": val_value,
        })
    return Ok(records)


def build_export(
    storage: StoragePort,
    generated_at: float,
    src_name: Optional[str] = None,
    lb_name: Optional[str] = None,
    until_dt: Optional[float] = None,
    include_archive: bool = False,
) -> Ok[dict] | Err[StorageError] | Err[NotFound]:
    """Build the exportable snapshot: {metadata, data}, per the format
    decided in docs/proposals/DATABASE_DESIGN.md ("Формат выгрузки снэпшотов")."""
    src_id = None
    if src_name is not None:
        found = _find_src(storage, src_name)
        if isinstance(found, Err):
            return found
        src_id = found.value

    lb_id = None
    if lb_name is not None:
        found = _find_lb(storage, lb_name)
        if isinstance(found, Err):
            return found
        lb_id = found.value

    state_r = build_state(
        storage, src_id=src_id, lb_id=lb_id, until_dt=until_dt, include_archive=include_archive,
    )
    if isinstance(state_r, Err):
        return state_r

    records_r = _state_to_records(storage, state_r.value)
    if isinstance(records_r, Err):
        return records_r

    return Ok({
        "metadata": {
            "generated_at": generated_at,
            "until_dt": until_dt,
            "include_archive": include_archive,
            "src": src_name,
            "lb": lb_name,
            "count": len(records_r.value),
        },
        "data": records_r.value,
    })


def export_state_file(
    storage: StoragePort,
    path: Path,
    generated_at: float,
    src_name: Optional[str] = None,
    lb_name: Optional[str] = None,
    until_dt: Optional[float] = None,
    include_archive: bool = False,
) -> Ok[int] | Err[StorageError] | Err[NotFound]:
    export_r = build_export(storage, generated_at, src_name, lb_name, until_dt, include_archive)
    if isinstance(export_r, Err):
        return export_r
    path.write_text(json.dumps(export_r.value, indent=2, ensure_ascii=False), encoding="utf-8")
    return Ok(export_r.value["metadata"]["count"])
