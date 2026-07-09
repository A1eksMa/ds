import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.domain.entities import TransactionInput, ValId
from src.domain.enums import Act
from src.domain.errors import StorageError
from src.domain.result import Err, Ok
from src.processing.engine import build_state

_TS = 1_700_000_000.0


@pytest.fixture
def db() -> InMemoryAdapter:
    return InMemoryAdapter()


def _insert(db, src, lb, id_, val, act, dt=_TS, p=1.0):
    return db.txn_insert(TransactionInput(act=act, dt=dt, src=src, lb=lb, id=id_, p=p, val=val))


def test_build_state_empty_storage_returns_empty_state(db):
    result = build_state(db)
    assert isinstance(result, Ok)
    assert result.value == {}


def test_build_state_reflects_latest_value(db):
    lb = db.lb_intern("email").value
    src = db.src_get_or_create("CRM", lb).value.src_id
    id_ = db.id_intern("1").value
    post = db.act_intern(Act.POST).value
    patch = db.act_intern(Act.PATCH).value
    v1 = db.val_intern("a@b.com").value
    v2 = db.val_intern("b@b.com").value

    _insert(db, src, lb, id_, v1, post, dt=_TS)
    _insert(db, src, lb, id_, v2, patch, dt=_TS + 1)

    result = build_state(db)
    assert isinstance(result, Ok)
    assert result.value[(src, lb, id_)] == v2


def test_build_state_filters_by_src(db):
    lb = db.lb_intern("email").value
    src_a = db.src_get_or_create("A", lb).value.src_id
    src_b = db.src_get_or_create("B", lb).value.src_id
    id_ = db.id_intern("1").value
    act = db.act_intern(Act.POST).value
    val = db.val_intern("v").value

    _insert(db, src_a, lb, id_, val, act)
    _insert(db, src_b, lb, id_, val, act)

    result = build_state(db, src_id=src_a)
    assert isinstance(result, Ok)
    assert set(result.value.keys()) == {(src_a, lb, id_)}


def test_build_state_filters_by_lb(db):
    lb_a = db.lb_intern("a").value
    lb_b = db.lb_intern("b").value
    src = db.src_get_or_create("S", lb_a).value.src_id
    id_ = db.id_intern("1").value
    act = db.act_intern(Act.POST).value
    val = db.val_intern("v").value

    _insert(db, src, lb_a, id_, val, act)
    _insert(db, src, lb_b, id_, val, act)

    result = build_state(db, lb_id=lb_a)
    assert isinstance(result, Ok)
    assert set(result.value.keys()) == {(src, lb_a, id_)}


def test_build_state_filters_by_id(db):
    lb = db.lb_intern("email").value
    src = db.src_get_or_create("S", lb).value.src_id
    id_a = db.id_intern("1").value
    id_b = db.id_intern("2").value
    act = db.act_intern(Act.POST).value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_a, val, act)
    _insert(db, src, lb, id_b, val, act)

    result = build_state(db, id_id=id_a)
    assert isinstance(result, Ok)
    assert set(result.value.keys()) == {(src, lb, id_a)}


def test_build_state_until_dt_ignores_later_transactions(db):
    lb = db.lb_intern("email").value
    src = db.src_get_or_create("S", lb).value.src_id
    id_ = db.id_intern("1").value
    post = db.act_intern(Act.POST).value
    patch = db.act_intern(Act.PATCH).value
    v1 = db.val_intern("v1").value
    v2 = db.val_intern("v2").value

    _insert(db, src, lb, id_, v1, post, dt=_TS)
    _insert(db, src, lb, id_, v2, patch, dt=_TS + 100)

    result = build_state(db, until_dt=_TS + 50)
    assert isinstance(result, Ok)
    assert result.value[(src, lb, id_)] == v1


def test_build_state_reconstructs_a_past_snapshot(db):
    # "Time machine": the same log, queried at three different points in
    # time, yields three different (correct) snapshots.
    lb = db.lb_intern("email").value
    src = db.src_get_or_create("S", lb).value.src_id
    id_ = db.id_intern("1").value
    post = db.act_intern(Act.POST).value
    patch = db.act_intern(Act.PATCH).value
    delete = db.act_intern(Act.DELETE).value
    v1 = db.val_intern("v1").value
    v2 = db.val_intern("v2").value

    _insert(db, src, lb, id_, v1, post, dt=_TS)
    _insert(db, src, lb, id_, v2, patch, dt=_TS + 10)
    _insert(db, src, lb, id_, ValId(0), delete, dt=_TS + 20)

    before_any = build_state(db, until_dt=_TS - 1).value
    after_post = build_state(db, until_dt=_TS).value
    after_patch = build_state(db, until_dt=_TS + 10).value
    after_delete = build_state(db, until_dt=_TS + 20).value

    assert (src, lb, id_) not in before_any
    assert after_post[(src, lb, id_)] == v1
    assert after_patch[(src, lb, id_)] == v2
    assert after_delete[(src, lb, id_)] == ValId(0)


def test_build_state_excludes_archived_transactions_by_default(db):
    lb = db.lb_intern("email").value
    src = db.src_get_or_create("S", lb).value.src_id
    id_ = db.id_intern("1").value
    act = db.act_intern(Act.POST).value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    db.txn_archive(until_dt=_TS + 1)

    result = build_state(db)
    assert isinstance(result, Ok)
    assert result.value == {}


def test_build_state_includes_archived_transactions_when_requested(db):
    lb = db.lb_intern("email").value
    src = db.src_get_or_create("S", lb).value.src_id
    id_ = db.id_intern("1").value
    act = db.act_intern(Act.POST).value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    db.txn_archive(until_dt=_TS + 1)

    result = build_state(db, include_archive=True)
    assert isinstance(result, Ok)
    assert result.value[(src, lb, id_)] == val


def test_build_state_propagates_storage_error(db, monkeypatch):
    def boom(*args, **kwargs):
        return Err(StorageError("boom"))

    monkeypatch.setattr(db, "txn_query", boom)
    result = build_state(db)
    assert isinstance(result, Err)
    assert result.error == StorageError("boom")
