import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import NotFound, ValidationError
from src.domain.result import Err, Ok
from src.service import load as svc_load
from src.service import mv as svc_mv

_T1 = 1_700_000_000.0
_T2 = 1_700_100_000.0


def _cfg(name="CRM", key_label="customer_id"):
    return SourceConfig(
        name=name, key_label=key_label, p=0.5,
        labels={key_label: LabelConfig(name=key_label)},
    )


@pytest.fixture
def db():
    return InMemoryAdapter()


def test_resolve_mv_unknown_src(db):
    r = svc_mv.resolve_mv(db, src_name="ERP", lb_name="x", to_src_name=None, to_lb_name="y")
    assert isinstance(r, Err)
    assert isinstance(r.error, NotFound)


def test_resolve_mv_unknown_lb(db):
    svc_load.load(db, {"customer_id": ["1"]}, _cfg(), _T1)
    r = svc_mv.resolve_mv(db, src_name="CRM", lb_name="no_such_label", to_src_name=None, to_lb_name="y")
    assert isinstance(r, Err)
    assert isinstance(r.error, NotFound)


def test_resolve_mv_refuses_key_label_as_source(db):
    svc_load.load(db, {"customer_id": ["1"]}, _cfg(), _T1)
    r = svc_mv.resolve_mv(db, src_name="CRM", lb_name="customer_id", to_src_name=None, to_lb_name="y")
    assert isinstance(r, Err)
    assert isinstance(r.error, ValidationError)


def test_resolve_mv_refuses_merge_into_key_label(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    r = svc_mv.resolve_mv(db, src_name="CRM", lb_name="email", to_src_name=None, to_lb_name="customer_id")
    assert isinstance(r, Err)
    assert isinstance(r.error, ValidationError)


def test_resolve_mv_refuses_same_label_as_destination(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    r = svc_mv.resolve_mv(db, src_name="CRM", lb_name="email", to_src_name=None, to_lb_name="email")
    assert isinstance(r, Err)
    assert isinstance(r.error, ValidationError)


def test_plan_has_no_side_effects(db):
    # resolving a plan for a brand-new destination source must not create it --
    # creation is deferred to apply_mv, so declining the confirmation prompt
    # (which never calls apply_mv) leaves the database untouched
    svc_load.load(db, {"customer_id": ["1"], "old_name": ["a"]}, _cfg(), _T1)
    plan_r = svc_mv.resolve_mv(db, src_name="CRM", lb_name="old_name", to_src_name="ERP", to_lb_name="new_name")
    assert isinstance(plan_r, Ok)
    assert plan_r.value.into_lb_id is None
    assert {s.name for s in db.src_list().value} == {"CRM"}


def test_rename_within_same_source(db):
    svc_load.load(db, {"customer_id": ["1", "2"], "old_name": ["a", "b"]}, _cfg(), _T1)
    plan_r = svc_mv.resolve_mv(db, src_name="CRM", lb_name="old_name", to_src_name=None, to_lb_name="new_name")
    assert isinstance(plan_r, Ok)
    plan = plan_r.value
    assert plan.into_lb_id is None  # new_name doesn't exist yet -- a straight rename

    count_r = svc_mv.count_matching(db, plan)
    assert count_r == Ok(2)

    result_r = svc_mv.apply_mv(db, plan)
    assert isinstance(result_r, Ok)
    assert result_r.value == 2

    lbs = db.lb_list().value
    assert "old_name" not in {lb.name for lb in lbs}
    assert "new_name" in {lb.name for lb in lbs}


def test_merge_into_existing_transition_label(db):
    # transition period: old_name fed data, then new_name started feeding data for
    # the same real-world concept while old_name was still in use for other keys
    svc_load.load(db, {"customer_id": ["1"], "old_name": ["a"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["2"], "new_name": ["b"]}, _cfg(), _T2)

    plan_r = svc_mv.resolve_mv(db, src_name="CRM", lb_name="old_name", to_src_name=None, to_lb_name="new_name")
    assert isinstance(plan_r, Ok)
    plan = plan_r.value
    assert plan.into_lb_id is not None  # new_name already has its own history -- a merge

    count_r = svc_mv.count_matching(db, plan)
    assert count_r == Ok(1)  # only old_name's own transaction, not new_name's

    result_r = svc_mv.apply_mv(db, plan)
    assert isinstance(result_r, Ok)
    assert result_r.value == 1

    lbs = db.lb_list().value
    assert "old_name" not in {lb.name for lb in lbs}
    new_lb = next(lb for lb in lbs if lb.name == "new_name")
    merged = db.txn_query(lb_ids=[new_lb.lb_id], include_archive=True).value
    assert len(merged) == 2  # both streams now under the same lb_id


def test_move_to_new_source_creates_it(db):
    svc_load.load(db, {"customer_id": ["1"], "old_name": ["a"]}, _cfg(), _T1)
    plan_r = svc_mv.resolve_mv(db, src_name="CRM", lb_name="old_name", to_src_name="ERP", to_lb_name="new_name")
    assert isinstance(plan_r, Ok)
    plan = plan_r.value
    assert plan.into_lb_id is None

    result_r = svc_mv.apply_mv(db, plan)
    assert isinstance(result_r, Ok)
    assert result_r.value == 1

    erp = next(s for s in db.src_list().value if s.name == "ERP")
    new_lb = next(lb for lb in db.lb_list(erp.src_id).value if lb.name == "new_name")
    txn = db.txn_query(src_id=erp.src_id).value[0]
    assert int(txn.lb) == int(new_lb.lb_id)
    assert int(txn.src) == int(erp.src_id)
