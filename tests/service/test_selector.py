import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import NotFound
from src.domain.result import Err, Ok
from src.service import selector as svc_selector
from src.service import load as svc_load

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


@pytest.fixture
def crm(db):
    """3 customers, one label flips status between batches; one row archived."""
    svc_load.load(db, {
        "customer_id": ["101", "102", "103"],
        "email": ["a@e.com", "b@e.com", "c@e.com"],
        "status": ["active", "inactive", "active"],
    }, _cfg(), _T1)
    svc_load.load(db, {
        "customer_id": ["102"],
        "status": ["active"],
    }, _cfg(), _T2)
    return db


def _lb_id(storage, src_name, lb_name):
    src = next(s for s in storage.src_list().value if s.name == src_name)
    lb = next(l for l in storage.lb_list(src.src_id).value if l.name == lb_name)
    return src.src_id, lb.lb_id


# --- resolve_selector: side-effect-free name resolution ---

def test_resolve_selector_unknown_source(crm):
    r = svc_selector.resolve_selector(crm, src_name="ERP")
    assert isinstance(r, Err)
    assert isinstance(r.error, NotFound)
    assert r.error.entity == "Source"


def test_resolve_selector_unknown_label(crm):
    r = svc_selector.resolve_selector(crm, src_name="CRM", lb_names=["fax"])
    assert isinstance(r, Err)
    assert r.error.entity == "Label"


def test_resolve_selector_unknown_id(crm):
    r = svc_selector.resolve_selector(crm, src_name="CRM", id_values=["999"])
    assert isinstance(r, Err)
    assert r.error.entity == "Id"


def test_resolve_selector_no_filters_means_everything(crm):
    r = svc_selector.resolve_selector(crm, src_name="CRM")
    assert isinstance(r, Ok)
    assert r.value.lb_ids is None
    assert r.value.id_ids is None
    assert r.value.cnts is None


def test_resolve_selector_lb_names(crm):
    r = svc_selector.resolve_selector(crm, src_name="CRM", lb_names=["email"])
    assert isinstance(r, Ok)
    assert len(r.value.lb_ids) == 1


def test_resolve_selector_id_values(crm):
    r = svc_selector.resolve_selector(crm, src_name="CRM", id_values=["101", "103"])
    assert isinstance(r, Ok)
    assert len(r.value.id_ids) == 2


# --- --where LB=VALUE: keys resolved via Level 1 fold ---

def test_resolve_selector_where_matches_current_folded_value(crm):
    # 102's status flips active in batch 2 -- --where must see the CURRENT value
    r = svc_selector.resolve_selector(crm, src_name="CRM", where=("status", "active"))
    assert isinstance(r, Ok)
    ids = {crm.id_get(i).value for i in r.value.id_ids}
    assert ids == {"101", "102", "103"}


def test_resolve_selector_where_no_match_is_empty_not_none(crm):
    r = svc_selector.resolve_selector(crm, src_name="CRM", where=("status", "on-hold"))
    assert isinstance(r, Ok)
    assert r.value.id_ids == []


def test_resolve_selector_where_unknown_label(crm):
    r = svc_selector.resolve_selector(crm, src_name="CRM", where=("fax", "x"))
    assert isinstance(r, Err)
    assert r.error.entity == "Label"


def test_resolve_selector_where_considers_archived_history(crm):
    # archive everything, then the fold must still see it (active+archived)
    crm.txn_archive(src_id=next(s.src_id for s in crm.src_list().value if s.name == "CRM"))
    r = svc_selector.resolve_selector(crm, src_name="CRM", where=("status", "active"))
    assert isinstance(r, Ok)
    assert len(r.value.id_ids) == 3


# --- --cnt: standalone selector, validated against the given source ---

def test_resolve_selector_cnt_selects_specific_rows(crm):
    src_id, _ = _lb_id(crm, "CRM", "email")
    one = crm.txn_query(src_id=src_id, include_archive=True).value[0]
    r = svc_selector.resolve_selector(crm, src_name="CRM", cnts=[int(one.cnt)])
    assert isinstance(r, Ok)
    assert r.value.cnts == [one.cnt]
    assert r.value.lb_ids is None and r.value.id_ids is None


def test_resolve_selector_cnt_unknown_is_notfound(crm):
    r = svc_selector.resolve_selector(crm, src_name="CRM", cnts=[999999])
    assert isinstance(r, Err)
    assert r.error.entity == "Transaction"


def test_resolve_selector_cnt_from_another_source_is_notfound(crm):
    svc_load.load(crm, {"customer_id": ["1"], "x": ["y"]}, _cfg(name="ERP", key_label="customer_id"), _T1)
    erp_src = next(s.src_id for s in crm.src_list().value if s.name == "ERP")
    erp_cnt = crm.txn_query(src_id=erp_src).value[0].cnt

    r = svc_selector.resolve_selector(crm, src_name="CRM", cnts=[int(erp_cnt)])
    assert isinstance(r, Err)
    assert r.error.entity == "Transaction"


# --- count_matching ---

def test_count_matching_whole_source_spans_active_and_archive(crm):
    src_id = next(s.src_id for s in crm.src_list().value if s.name == "CRM")
    crm.txn_archive(src_id=src_id, until_dt=_T1 + 1)
    selector = svc_selector.resolve_selector(crm, src_name="CRM").value
    r = svc_selector.count_matching(crm, selector)
    assert isinstance(r, Ok)
    assert r.value == len(crm.txn_query(src_id=src_id, include_archive=True).value)


def test_count_matching_narrows_with_lb(crm):
    whole = svc_selector.count_matching(crm, svc_selector.resolve_selector(crm, src_name="CRM").value)
    one_label = svc_selector.count_matching(
        crm, svc_selector.resolve_selector(crm, src_name="CRM", lb_names=["status"]).value
    )
    assert 0 < one_label.value < whole.value


def test_count_matching_where_selector_matches_txn_archive_result(crm):
    selector = svc_selector.resolve_selector(crm, src_name="CRM", where=("status", "active")).value
    previewed = svc_selector.count_matching(crm, selector).value

    moved = crm.txn_archive(
        src_id=selector.src_id, lb_ids=selector.lb_ids, id_ids=selector.id_ids,
    ).value
    assert moved == previewed
