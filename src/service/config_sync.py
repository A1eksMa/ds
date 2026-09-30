from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Union

from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import NotFound, StorageError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort
from src.service.selector import resolve_src

_Err = Union[Err[StorageError], Err[NotFound]]


@dataclass(frozen=True)
class SyncResult:
    cfg: SourceConfig
    added: List[str]
    removed: List[str]


def sync_labels(storage: StoragePort, cfg: SourceConfig) -> Union[Ok[SyncResult], _Err]:
    """Refresh cfg.labels against what the database currently holds for this
    source (`ds update <source_dir>`):

    - a label with data (active or archived transactions) but not yet
      declared -> added as a bare {"name": ...} entry (type "text",
      archive/publish at their defaults) -- ds has no way to guess a real
      type, that's for a human to fill in afterwards;
    - a declared label with NO data left at all (e.g. fully hard-deleted via
      `ds delete`) -> removed;
    - a declared label that still has data keeps its existing entry
      untouched (type/archive/publish/p/description are never overwritten).

    `cfg.key_label` is exempt from removal: it never has transactions of its
    own (see service/load.py), so "no data" is trivially true for it and it
    would otherwise be dropped on every run if a user had documented it.
    """
    src_r = resolve_src(storage, cfg.name)
    if isinstance(src_r, Err):
        return src_r
    src_id = src_r.value.src_id

    txns_r = storage.txn_query(src_id=src_id, include_archive=True)
    if isinstance(txns_r, Err):
        return txns_r
    lb_ids_with_data = {int(t.lb) for t in txns_r.value}

    lbs_r = storage.lb_list(src_id)
    if isinstance(lbs_r, Err):
        return lbs_r
    name_by_lbid = {int(lb.lb_id): lb.name for lb in lbs_r.value}
    names_with_data = {name_by_lbid[lb] for lb in lb_ids_with_data if lb in name_by_lbid}

    labels = dict(cfg.labels)

    removed: List[str] = []
    for name in list(labels):
        if name == cfg.key_label:
            continue
        if name not in names_with_data:
            del labels[name]
            removed.append(name)

    added: List[str] = []
    for name in names_with_data:
        if name not in labels:
            labels[name] = LabelConfig(name=name)
            added.append(name)

    return Ok(SyncResult(
        cfg=replace(cfg, labels=labels),
        added=sorted(added),
        removed=sorted(removed),
    ))
