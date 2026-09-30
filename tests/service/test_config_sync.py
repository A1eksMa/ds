import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import NotFound
from src.domain.result import Err, Ok
from src.service import config_sync as svc_config_sync
from src.service import load as svc_load

_T1 = 1_700_000_000.0


def _cfg(labels=None, key_label="customer_id", name="CRM"):
    labels = dict(labels or {})
    labels.setdefault(key_label, LabelConfig(name=key_label))
    return SourceConfig(name=name, key_label=key_label, labels=labels)


@pytest.fixture
def db():
    return InMemoryAdapter()


def test_sync_unknown_source_is_notfound(db):
    r = svc_config_sync.sync_labels(db, _cfg(name="ERP"))
    assert isinstance(r, Err)
    assert isinstance(r.error, NotFound)


def test_sync_adds_undeclared_label_that_has_data(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)

    r = svc_config_sync.sync_labels(db, _cfg())  # config only knows the key label
    assert isinstance(r, Ok)
    assert r.value.added == ["email"]
    assert r.value.removed == []
    assert "email" in r.value.cfg.labels
    assert r.value.cfg.labels["email"].type == "text"  # ds can't guess a real type


def test_sync_removes_declared_label_with_no_data(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    src_id = next(s.src_id for s in db.src_list().value if s.name == "CRM")
    lb_id = next(l.lb_id for l in db.lb_list(src_id).value if l.name == "email")
    db.txn_delete(src_id=src_id, lb_ids=[lb_id])  # fully removed now

    cfg = _cfg({"email": LabelConfig(name="email", type="text")})
    r = svc_config_sync.sync_labels(db, cfg)
    assert isinstance(r, Ok)
    assert r.value.removed == ["email"]
    assert r.value.added == []
    assert "email" not in r.value.cfg.labels


def test_sync_keeps_existing_entry_untouched_when_data_still_present(db):
    svc_load.load(db, {"customer_id": ["1"], "revenue": ["100"]}, _cfg(), _T1)

    declared = LabelConfig(name="revenue", type="number", archive=True, p=0.9, description="x")
    cfg = _cfg({"revenue": declared})
    r = svc_config_sync.sync_labels(db, cfg)
    assert isinstance(r, Ok)
    assert r.value.added == []
    assert r.value.removed == []
    assert r.value.cfg.labels["revenue"] == declared  # byte-for-byte preserved


def test_sync_key_label_is_exempt_from_removal(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    # key_label itself never has transactions -- must not be treated as "gone"
    cfg = _cfg()  # already includes customer_id per the _cfg() helper
    r = svc_config_sync.sync_labels(db, cfg)
    assert isinstance(r, Ok)
    assert "customer_id" not in r.value.removed
    assert "customer_id" in r.value.cfg.labels


def test_sync_archived_only_label_is_not_removed(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    src_id = next(s.src_id for s in db.src_list().value if s.name == "CRM")
    db.txn_archive(src_id=src_id)  # moved, not deleted

    cfg = _cfg({"email": LabelConfig(name="email")})
    r = svc_config_sync.sync_labels(db, cfg)
    assert isinstance(r, Ok)
    assert r.value.removed == []
    assert "email" in r.value.cfg.labels


def test_sync_no_op_when_already_in_sync(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    cfg = _cfg({"email": LabelConfig(name="email")})
    r = svc_config_sync.sync_labels(db, cfg)
    assert isinstance(r, Ok)
    assert r.value.added == []
    assert r.value.removed == []
