from __future__ import annotations

import json
from pathlib import Path

from src.config.models import SourceConfig
from src.domain.entities import TransactionInput, ValId
from src.domain.enums import Act
from src.domain.errors import StorageError, ValidationError
from src.domain.result import Err, Ok
from src.loader import validator as tbl_validator
from src.ports.storage_port import StoragePort


def load(
    storage: StoragePort,
    data: dict,
    cfg: SourceConfig,
    dt: float,
    act: Act = Act.POST,
) -> Ok[int] | Err[StorageError] | Err[ValidationError]:
    val_result = tbl_validator.validate_table(data, cfg)
    if isinstance(val_result, Err):
        return val_result

    storage.begin()

    act_r = storage.act_intern(act)
    if isinstance(act_r, Err):
        storage.rollback()
        return act_r
    act_id = act_r.value

    key_lb_r = storage.lb_intern(cfg.key_label)
    if isinstance(key_lb_r, Err):
        storage.rollback()
        return key_lb_r

    src_r = storage.src_get_or_create(cfg.name, key_lb_r.value)
    if isinstance(src_r, Err):
        storage.rollback()
        return src_r
    src_id = src_r.value.src_id

    lb_ids: dict[str, object] = {cfg.key_label: key_lb_r.value}
    for col in data:
        if col == cfg.key_label:
            continue
        lb_r = storage.lb_intern(col)
        if isinstance(lb_r, Err):
            storage.rollback()
            return lb_r
        lb_ids[col] = lb_r.value

    count = 0
    for i in range(len(data[cfg.key_label])):
        id_r = storage.id_intern(str(data[cfg.key_label][i]))
        if isinstance(id_r, Err):
            storage.rollback()
            return id_r
        id_id = id_r.value

        for col in data:
            if col == cfg.key_label:
                continue

            raw = data[col][i]
            if raw is None:
                val_id = ValId(0)
            else:
                val_r = storage.val_intern(str(raw))
                if isinstance(val_r, Err):
                    storage.rollback()
                    return val_r
                val_id = val_r.value

            txn_r = storage.txn_insert(TransactionInput(
                act=act_id, dt=dt,
                src=src_id, lb=lb_ids[col], id=id_id,
                p=1.0, val=val_id,
            ))
            if isinstance(txn_r, Err):
                storage.rollback()
                return txn_r
            count += 1

    storage.commit()
    return Ok(count)


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
