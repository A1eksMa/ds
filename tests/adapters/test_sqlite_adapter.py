import pytest

from src.adapters.sqlite_adapter import SQLiteAdapter
from src.domain.entities import LbId, Src, SrcId, TransactionInput, ValId
from src.domain.enums import Act
from src.domain.errors import StorageError
from src.domain.result import Err, Ok

_TS = 1_700_000_000.0


@pytest.fixture
def db(tmp_path) -> SQLiteAdapter:
    return SQLiteAdapter(str(tmp_path / "test.db"))


# --- Schema & pool caching ---

def test_schema_initializes_without_error(db):
    result = db.lb_list()
    assert isinstance(result, Ok)


def test_lb_intern_caches_on_first_call(db):
    first = db.lb_intern("email").value
    second = db.lb_intern("email").value
    assert first == second


def test_lb_intern_different_names_different_ids(db):
    a = db.lb_intern("email").value
    b = db.lb_intern("phone").value
    assert a != b


def test_id_intern_same_value_same_id(db):
    assert db.id_intern("42").value == db.id_intern("42").value


def test_val_intern_no_cache_same_id(db):
    v1 = db.val_intern("hello").value
    v2 = db.val_intern("hello").value
    assert v1 == v2


def test_act_intern_all_variants(db):
    for act in Act:
        result = db.act_intern(act)
        assert isinstance(result, Ok)


def test_act_intern_consistent_across_calls(db):
    a = db.act_intern(Act.POST).value
    b = db.act_intern(Act.POST).value
    assert a == b


# --- Source metadata ---

def test_src_get_or_create_persists(db):
    lb_id = db.lb_intern("cid").value
    result = db.src_get_or_create("CRM", lb_id)
    assert isinstance(result, Ok)
    assert result.value.name == "CRM"
    assert result.value.key_label == lb_id


def test_src_get_or_create_idempotent(db):
    lb_id = db.lb_intern("cid").value
    s1 = db.src_get_or_create("CRM", lb_id).value.src_id
    s2 = db.src_get_or_create("CRM", lb_id).value.src_id
    assert s1 == s2


def test_src_get_not_found(db):
    result = db.src_get(SrcId(9999))
    assert isinstance(result, Err)
    assert isinstance(result.error, StorageError)


def test_src_update_persists_changes(db):
    lb_id = db.lb_intern("id").value
    src = db.src_get_or_create("ERP", lb_id).value
    updated = Src(src_id=src.src_id, name=src.name, p=0.95, key_label=src.key_label, description="ERP")
    db.src_update(updated)
    refreshed = db.src_get(src.src_id).value
    assert refreshed.p == 0.95
    assert refreshed.description == "ERP"


def test_src_list_returns_all(db):
    lb_id = db.lb_intern("id").value
    db.src_get_or_create("CRM", lb_id)
    db.src_get_or_create("ERP", lb_id)
    names = {s.name for s in db.src_list().value}
    assert {"CRM", "ERP"}.issubset(names)


# --- Label metadata ---

def test_lb_get_returns_label(db):
    lb_id = db.lb_intern("email").value
    result = db.lb_get(lb_id)
    assert isinstance(result, Ok)
    assert result.value.name == "email"


def test_lb_get_not_found(db):
    result = db.lb_get(LbId(9999))
    assert isinstance(result, Err)


def test_lb_update_persists(db):
    from src.domain.entities import Lb
    lb_id = db.lb_intern("price").value
    lb = db.lb_get(lb_id).value
    updated = Lb(lb_id=lb.lb_id, name=lb.name, p=0.8, description="Unit price")
    db.lb_update(updated)
    refreshed = db.lb_get(lb_id).value
    assert refreshed.p == 0.8
    assert refreshed.description == "Unit price"


# --- Transactions ---

def _insert(db, src_id, lb_id, id_id, val_id, act_id, dt=_TS, p=1.0):
    return db.txn_insert(TransactionInput(
        act=act_id, dt=dt, src=src_id,
        lb=lb_id, id=id_id, p=p, val=val_id,
    ))


def test_txn_insert_returns_transaction_with_cnt(db):
    lb = db.lb_intern("email").value
    src = db.src_get_or_create("CRM", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("a@b.com").value

    result = _insert(db, src, lb, id_, val, act)
    assert isinstance(result, Ok)
    assert result.value.cnt is not None


def test_txn_insert_cnt_is_unique(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    t1 = _insert(db, src, lb, id_, val, act).value
    t2 = _insert(db, src, lb, id_, val, act).value
    assert t1.cnt != t2.cnt


def test_txn_query_filters_by_src(db):
    lb = db.lb_intern("x").value
    src_a = db.src_get_or_create("A", lb).value.src_id
    src_b = db.src_get_or_create("B", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src_a, lb, id_, val, act)
    _insert(db, src_b, lb, id_, val, act)

    result = db.txn_query(src_id=src_a)
    assert isinstance(result, Ok)
    assert len(result.value) == 1
    assert result.value[0].src == src_a


def test_txn_query_filters_by_until_dt(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    _insert(db, src, lb, id_, val, act, dt=_TS + 200)

    result = db.txn_query(until_dt=_TS + 100)
    assert isinstance(result, Ok)
    assert len(result.value) == 1
    assert result.value[0].dt == _TS


def test_txn_archive_is_atomic(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    _insert(db, src, lb, id_, val, act, dt=_TS + 200)

    arch = db.txn_archive(until_dt=_TS + 100)
    assert isinstance(arch, Ok)
    assert arch.value == 1

    active = db.txn_query().value
    assert len(active) == 1

    full = db.txn_query(include_archive=True).value
    assert len(full) == 2


def test_txn_delete_removes_from_both_tables(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    db.txn_archive(until_dt=_TS + 1)
    _insert(db, src, lb, id_, val, act, dt=_TS + 200)

    db.txn_delete(src_id=src)
    assert db.txn_query(include_archive=True).value == []


