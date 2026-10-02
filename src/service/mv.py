from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from src.domain.entities import LbId
from src.domain.errors import NotFound, StorageError, ValidationError
from src.domain.result import Err, Ok
from src.ports.storage_port import StoragePort
from src.service.selector import resolve_src

_Err = Union[Err[StorageError], Err[NotFound], Err[ValidationError]]


@dataclass(frozen=True)
class MvPlan:
    """Read-only resolution of `ds mv` -- nothing is created or mutated yet.
    into_lb_id is None when the destination label doesn't exist yet (a
    straight rename); apply_mv creates whatever is missing (source and/or
    label) only once the caller has confirmed, so declining the prompt
    leaves the database untouched."""
    from_lb_id: LbId
    to_src_name: str
    to_lb_name: str
    into_lb_id: Optional[LbId]


def resolve_mv(
    storage: StoragePort,
    *,
    src_name: str,
    lb_name: str,
    to_src_name: Optional[str],
    to_lb_name: str,
) -> Union[Ok[MvPlan], _Err]:
    """Resolve `ds mv --src SRC --lb LB [--to-src SRC2] --to-lb LB2`. Mirrors
    Linux `mv`: a destination label that doesn't exist yet means a straight
    rename; one that already has its own history (e.g. a transition period
    where both the old and new name fed data side by side) gets merged with
    it. The key label of either source can never be the --lb or the --to-lb
    -- it has no transactions of its own (see service/config_sync.py) and
    Src.key_label must keep pointing at a stable row.
    """
    src_r = resolve_src(storage, src_name)
    if isinstance(src_r, Err):
        return src_r
    src = src_r.value

    lbs_r = storage.lb_list(src.src_id)
    if isinstance(lbs_r, Err):
        return lbs_r
    from_lb = next((lb for lb in lbs_r.value if lb.name == lb_name), None)
    if from_lb is None:
        return Err(NotFound(entity="Label", key=lb_name))
    if from_lb.lb_id == src.key_label:
        return Err(ValidationError(
            field="lb", message=f"'{lb_name}' is the key label of '{src_name}' -- cannot mv it",
        ))

    to_src_name = to_src_name or src_name
    to_src_r = resolve_src(storage, to_src_name)
    if isinstance(to_src_r, Err) and not isinstance(to_src_r.error, NotFound):
        return to_src_r

    into_lb_id: Optional[LbId] = None
    if not isinstance(to_src_r, Err):
        to_src = to_src_r.value
        to_lbs_r = storage.lb_list(to_src.src_id)
        if isinstance(to_lbs_r, Err):
            return to_lbs_r
        existing = next((lb for lb in to_lbs_r.value if lb.name == to_lb_name), None)
        if existing is not None:
            if existing.lb_id == to_src.key_label:
                return Err(ValidationError(
                    field="to_lb",
                    message=f"'{to_lb_name}' is the key label of '{to_src_name}' -- cannot mv into it",
                ))
            if existing.lb_id == from_lb.lb_id:
                return Err(ValidationError(
                    field="to_lb",
                    message="--src/--lb and --to-src/--to-lb resolve to the same label -- nothing to do",
                ))
            into_lb_id = existing.lb_id

    return Ok(MvPlan(
        from_lb_id=from_lb.lb_id, to_src_name=to_src_name, to_lb_name=to_lb_name,
        into_lb_id=into_lb_id,
    ))


def count_matching(storage: StoragePort, plan: MvPlan) -> Union[Ok[int], Err[StorageError]]:
    """How many transactions (active + archived) --lb currently has -- shown as
    a preview before the confirmation prompt, same idea as
    selector.py::count_matching for delete/archive/unarchive."""
    txns_r = storage.txn_query(lb_ids=[plan.from_lb_id], include_archive=True)
    if isinstance(txns_r, Err):
        return txns_r
    return Ok(len(txns_r.value))


def apply_mv(storage: StoragePort, plan: MvPlan) -> Union[Ok[int], Err[StorageError]]:
    """Materialise the plan: create the destination source/label if either
    didn't exist yet (same auto-create as `ds load`'s src_get_or_create/
    lb_intern), then StoragePort.lb_merge repoints every transaction (active +
    archived) from the old label onto the destination and retires the
    now-orphaned old lbs row."""
    into_lb_id = plan.into_lb_id
    if into_lb_id is None:
        to_src_r = storage.src_get_or_create(plan.to_src_name)
        if isinstance(to_src_r, Err):
            return to_src_r
        into_lb_r = storage.lb_intern(plan.to_lb_name, to_src_r.value.src_id)
        if isinstance(into_lb_r, Err):
            return into_lb_r
        into_lb_id = into_lb_r.value
    return storage.lb_merge(plan.from_lb_id, into_lb_id)
