import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import NotFound
from src.domain.result import Err, Ok
from src.service import delete as svc_delete
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
    """CRM with two labels, one batch active + one archived (mirrors the
    scenario lifecycle-cli.md cares about: delete must reach both tables)."""
    svc_load.load(db, {
        "customer_id": ["101", "102"],
        "email": ["alice@e.com", "bob@e.com"],
        "phone": ["+1", "+2"],
    }, _cfg(), _T1)
    db.txn_archive(until_dt=_T1 + 1)
    svc_load.load(db, {
        "customer_id": ["101"],
        "email": ["alice.new@e.com"],
    }, _cfg(), _T2)
    return db


# --- resolve_target: side-effect-free name resolution (mirrors ds get) ------

def test_resolve_target_unknown_source_is_notfound(crm):
    r = svc_delete.resolve_target(crm, "ERP")
    assert isinstance(r, Err)
    assert isinstance(r.error, NotFound)
    assert r.error.entity == "Source"
    assert r.error.key == "ERP"


def test_resolve_target_unknown_source_creates_no_record(crm):
    before = {s.name for s in crm.src_list().value}
    svc_delete.resolve_target(crm, "ERP")
    after = {s.name for s in crm.src_list().value}
    assert after == before
    assert "ERP" not in after


def test_resolve_target_unknown_label_is_notfound(crm):
    r = svc_delete.resolve_target(crm, "CRM", "fax")
    assert isinstance(r, Err)
    assert isinstance(r.error, NotFound)
    assert r.error.entity == "Label"
    assert r.error.key == "CRM.fax"


def test_resolve_target_src_only(crm):
    r = svc_delete.resolve_target(crm, "CRM")
    assert isinstance(r, Ok)
    assert r.value.lb_id is None


def test_resolve_target_src_and_lb(crm):
    r = svc_delete.resolve_target(crm, "CRM", "email")
    assert isinstance(r, Ok)
    assert r.value.lb_id is not None


# --- count_matching: preview before the irreversible delete -----------------

def test_count_matching_whole_source_spans_active_and_archive(crm):
    target = svc_delete.resolve_target(crm, "CRM").value
    r = svc_delete.count_matching(crm, target)
    assert isinstance(r, Ok)
    # whole-source count must equal a full include_archive query (active + archived)
    expected = len(crm.txn_query(include_archive=True).value)
    assert r.value == expected
    assert r.value > 0


def test_count_matching_single_label_is_narrower_than_whole_source(crm):
    whole = svc_delete.count_matching(crm, svc_delete.resolve_target(crm, "CRM").value)
    one_label = svc_delete.count_matching(crm, svc_delete.resolve_target(crm, "CRM", "phone").value)
    assert isinstance(one_label, Ok)
    assert 0 < one_label.value < whole.value


# --- count_matching + txn_delete agree (the preview isn't a lie) ------------

def test_count_matching_matches_what_txn_delete_actually_removes(crm):
    target = svc_delete.resolve_target(crm, "CRM", "email").value
    previewed = svc_delete.count_matching(crm, target).value
    deleted = crm.txn_delete(src_id=target.src_id, lb_id=target.lb_id).value
    assert deleted == previewed
    assert svc_delete.count_matching(crm, target).value == 0
