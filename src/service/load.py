from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple, Union

from src.config.models import SourceConfig
from src.domain.entities import ActId, IdId, LbId, TransactionInput, ValId
from src.domain.enums import Act
from src.domain.errors import StorageError, ValidationError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort
from src.service import validate as tbl_validator


def _act_id(
    storage: StoragePort, cache: Dict[Act, ActId], act: Act
) -> Union[Ok[ActId], Err[StorageError]]:
    if act in cache:
        return Ok(cache[act])
    result = storage.act_intern(act)
    if isinstance(result, Ok):
        cache[act] = result.value
    return result


def load(
    storage: StoragePort,
    data: dict,
    cfg: SourceConfig,
    dt: float,
) -> Ok[int] | Err[StorageError] | Err[ValidationError]:
    """Load a columnar JSON table, auto-detecting act per cell:
    - raw value is null            -> DELETE
    - no prior value for (lb, id)  -> PATCH (first appearance, or reappearance after a delete)
    - a prior value exists         -> POST  (overwriting an existing value)

    A column whose label is declared `"archive": true` in cfg.labels is inserted
    straight into transactions_archive instead of transactions (act detection still
    sees archived history via txn_last_values, so PATCH/POST stays correct either way).
    Columns not declared in cfg.labels are unaffected -- auto-interned as before.
    """
    val_result = tbl_validator.validate_table(data, cfg)
    if isinstance(val_result, Err):
        return val_result

    storage.begin()

    act_cache: Dict[Act, ActId] = {}

    # Src must exist before its key label can be interned (Lb.src is a required
    # FK), and Src.key_label can't be set until that label exists -- so the
    # source is created first with key_label left unset, then bootstrapped.
    src_r = storage.src_get_or_create(cfg.name)
    if isinstance(src_r, Err):
        storage.rollback()
        return src_r
    src = src_r.value
    src_id = src.src_id

    key_lb_r = storage.lb_intern(cfg.key_label, src_id)
    if isinstance(key_lb_r, Err):
        storage.rollback()
        return key_lb_r

    if src.key_label is None:
        set_r = storage.src_set_key_label(src_id, key_lb_r.value)
        if isinstance(set_r, Err):
            storage.rollback()
            return set_r

    lb_ids: Dict[str, LbId] = {cfg.key_label: key_lb_r.value}
    for col in data:
        if col == cfg.key_label:
            continue
        lb_r = storage.lb_intern(col, src_id)
        if isinstance(lb_r, Err):
            storage.rollback()
            return lb_r
        lb_ids[col] = lb_r.value

    id_ids: list = []
    for raw_id in data[cfg.key_label]:
        id_r = storage.id_intern(str(raw_id))
        if isinstance(id_r, Err):
            storage.rollback()
            return id_r
        id_ids.append(id_r.value)

    non_key_lb_ids = [lb_ids[col] for col in data if col != cfg.key_label]
    last_r = storage.txn_last_values(src_id, non_key_lb_ids, id_ids)
    if isinstance(last_r, Err):
        storage.rollback()
        return last_r
    last_values: Dict[Tuple[LbId, IdId], ValId] = last_r.value

    count = 0
    for i, id_id in enumerate(id_ids):
        for col in data:
            if col == cfg.key_label:
                continue

            lb_id = lb_ids[col]
            raw = data[col][i]

            if raw is None:
                act = Act.DELETE
                val_id = ValId(0)
            else:
                val_r = storage.val_intern(str(raw))
                if isinstance(val_r, Err):
                    storage.rollback()
                    return val_r
                val_id = val_r.value
                last_val = last_values.get((lb_id, id_id), ValId(0))
                act = Act.PATCH if int(last_val) == 0 else Act.POST

            act_r = _act_id(storage, act_cache, act)
            if isinstance(act_r, Err):
                storage.rollback()
                return act_r

            label_cfg = cfg.labels.get(col)
            archived = label_cfg is not None and label_cfg.archive

            txn_r = storage.txn_insert(TransactionInput(
                act=act_r.value, dt=dt,
                src=src_id, lb=lb_id, id=id_id,
                p=1.0, val=val_id,
            ), archived=archived)
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
) -> Ok[int] | Err[StorageError] | Err[ValidationError]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Err(StorageError(str(exc)))
    return load(storage, data, cfg, dt)
