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


def _src(db, name="S") -> SrcId:
    return db.src_get_or_create(name).value.src_id


# --- Schema & pool caching ---

def test_schema_initializes_without_error(db):
    result = db.lb_list()
    assert isinstance(result, Ok)


def test_lb_intern_caches_on_first_call(db):
    src = _src(db)
    first = db.lb_intern("email", src).value
    second = db.lb_intern("email", src).value
    assert first == second


def test_lb_intern_different_names_different_ids(db):
    src = _src(db)
    a = db.lb_intern("email", src).value
    b = db.lb_intern("phone", src).value
    assert a != b


def test_lb_intern_same_name_different_sources_different_ids(db):
    src_a = _src(db, "A")
    src_b = _src(db, "B")
    a = db.lb_intern("email", src_a).value
    b = db.lb_intern("email", src_b).value
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
    result = db.src_get_or_create("CRM")
    assert isinstance(result, Ok)
    assert result.value.name == "CRM"
    assert result.value.key_label is None


def test_src_get_or_create_idempotent(db):
    s1 = db.src_get_or_create("CRM").value.src_id
    s2 = db.src_get_or_create("CRM").value.src_id
    assert s1 == s2


def test_src_get_not_found(db):
    result = db.src_get(SrcId(9999))
    assert isinstance(result, Err)
    assert isinstance(result.error, StorageError)


def test_src_set_key_label_persists(db):
    src = db.src_get_or_create("CRM").value
    lb_id = db.lb_intern("cid", src.src_id).value
    result = db.src_set_key_label(src.src_id, lb_id)
    assert isinstance(result, Ok)
    refreshed = db.src_get(src.src_id).value
    assert refreshed.key_label == lb_id


def test_src_update_persists_changes(db):
    src = db.src_get_or_create("ERP").value
    updated = Src(src_id=src.src_id, name=src.name, p=0.95, key_label=src.key_label, description="ERP")
    db.src_update(updated)
    refreshed = db.src_get(src.src_id).value
    assert refreshed.p == 0.95
    assert refreshed.description == "ERP"


def test_src_list_returns_all(db):
    db.src_get_or_create("CRM")
    db.src_get_or_create("ERP")
    names = {s.name for s in db.src_list().value}
    assert {"CRM", "ERP"}.issubset(names)


# --- Label metadata ---

def test_lb_get_returns_label(db):
    src = _src(db)
    lb_id = db.lb_intern("email", src).value
    result = db.lb_get(lb_id)
    assert isinstance(result, Ok)
    assert result.value.name == "email"
    assert result.value.src == src


def test_lb_get_not_found(db):
    result = db.lb_get(LbId(9999))
    assert isinstance(result, Err)


def test_lb_update_persists(db):
    from src.domain.entities import Lb
    src = _src(db)
    lb_id = db.lb_intern("price", src).value
    lb = db.lb_get(lb_id).value
    updated = Lb(lb_id=lb.lb_id, name=lb.name, p=0.8, src=lb.src, description="Unit price")
    db.lb_update(updated)
    refreshed = db.lb_get(lb_id).value
    assert refreshed.p == 0.8
    assert refreshed.description == "Unit price"


def test_lb_list_filters_by_src(db):
    src_a = _src(db, "A")
    src_b = _src(db, "B")
    db.lb_intern("email", src_a)
    db.lb_intern("phone", src_b)

    result = db.lb_list(src_id=src_a)
    assert isinstance(result, Ok)
    names = {lb.name for lb in result.value}
    assert names == {"email"}


# --- Transactions ---

def _insert(db, src_id, lb_id, id_id, val_id, act_id, dt=_TS, p=1.0):
    return db.txn_insert(TransactionInput(
        act=act_id, dt=dt, src=src_id,
        lb=lb_id, id=id_id, p=p, val=val_id,
    ))


def test_txn_insert_returns_transaction_with_cnt(db):
    src = _src(db, "CRM")
    lb = db.lb_intern("email", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("a@b.com").value

    result = _insert(db, src, lb, id_, val, act)
    assert isinstance(result, Ok)
    assert result.value.cnt is not None


def test_txn_insert_populates_created_at(db):
    src = _src(db, "CRM")
    lb = db.lb_intern("email", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("a@b.com").value

    txn = _insert(db, src, lb, id_, val, act).value
    assert txn.created_at is not None

    stored = db.txn_query().value[0]
    assert stored.created_at == txn.created_at


def test_txn_insert_cnt_is_unique(db):
    src = _src(db)
    lb = db.lb_intern("x", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    t1 = _insert(db, src, lb, id_, val, act).value
    t2 = _insert(db, src, lb, id_, val, act).value
    assert t1.cnt != t2.cnt


def test_txn_insert_archived_goes_straight_to_archive(db):
    src = _src(db)
    lb = db.lb_intern("x", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    result = db.txn_insert(
        TransactionInput(act=act, dt=_TS, src=src, lb=lb, id=id_, p=1.0, val=val),
        archived=True,
    )
    assert isinstance(result, Ok)
    assert db.txn_query().value == []
    assert len(db.txn_query(include_archive=True).value) == 1


def test_txn_query_filters_by_src(db):
    src_a = _src(db, "A")
    src_b = _src(db, "B")
    lb = db.lb_intern("x", src_a).value
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
    src = _src(db)
    lb = db.lb_intern("x", src).value
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
    src = _src(db)
    lb = db.lb_intern("x", src).value
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


def test_txn_archive_preserves_created_at(db):
    src = _src(db)
    lb = db.lb_intern("x", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    inserted = _insert(db, src, lb, id_, val, act, dt=_TS).value
    db.txn_archive(until_dt=_TS + 1)

    archived = db.txn_query(include_archive=True).value[0]
    assert archived.created_at == inserted.created_at


def test_txn_delete_removes_from_both_tables(db):
    src = _src(db)
    lb = db.lb_intern("x", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    db.txn_archive(until_dt=_TS + 1)
    _insert(db, src, lb, id_, val, act, dt=_TS + 200)

    # regression: txn_delete used to report only the active-table rowcount,
    # silently undercounting when matching rows also existed in the archive
    result = db.txn_delete(src_id=src)
    assert isinstance(result, Ok)
    assert result.value == 2
    assert db.txn_query(include_archive=True).value == []


# --- txn_last_values ---

def test_txn_last_values_empty_when_no_history(db):
    src = _src(db, "CRM")
    lb = db.lb_intern("email", src).value
    id_ = db.id_intern("1").value

    result = db.txn_last_values(src, [lb], [id_])
    assert isinstance(result, Ok)
    assert result.value == {}


def test_txn_last_values_returns_most_recent(db):
    src = _src(db, "CRM")
    lb = db.lb_intern("email", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    v1 = db.val_intern("a@b.com").value
    v2 = db.val_intern("b@b.com").value

    _insert(db, src, lb, id_, v1, act, dt=_TS)
    _insert(db, src, lb, id_, v2, act, dt=_TS + 1)

    result = db.txn_last_values(src, [lb], [id_])
    assert isinstance(result, Ok)
    assert result.value[(lb, id_)] == v2


def test_txn_last_values_reflects_delete(db):
    src = _src(db, "CRM")
    lb = db.lb_intern("email", src).value
    act = db.act_intern(Act.DELETE).value
    id_ = db.id_intern("1").value

    _insert(db, src, lb, id_, ValId(0), act, dt=_TS)

    result = db.txn_last_values(src, [lb], [id_])
    assert isinstance(result, Ok)
    assert int(result.value[(lb, id_)]) == 0


def test_txn_last_values_includes_archived(db):
    src = _src(db, "CRM")
    lb = db.lb_intern("email", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("a@b.com").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    db.txn_archive(until_dt=_TS + 1)

    result = db.txn_last_values(src, [lb], [id_])
    assert isinstance(result, Ok)
    assert result.value[(lb, id_)] == val


def test_txn_last_values_filters_by_src(db):
    src_a = _src(db, "A")
    src_b = _src(db, "B")
    lb = db.lb_intern("email", src_a).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("a@b.com").value

    _insert(db, src_a, lb, id_, val, act, dt=_TS)

    result = db.txn_last_values(src_b, [lb], [id_])
    assert isinstance(result, Ok)
    assert result.value == {}


def test_txn_last_values_empty_id_list_returns_empty(db):
    src = _src(db, "CRM")
    lb = db.lb_intern("email", src).value

    result = db.txn_last_values(src, [lb], [])
    assert isinstance(result, Ok)
    assert result.value == {}


def test_txn_last_values_multiple_ids_and_labels(db):
    src = _src(db, "CRM")
    lb_a = db.lb_intern("email", src).value
    lb_b = db.lb_intern("phone", src).value
    act = db.act_intern(Act.POST).value
    id_1 = db.id_intern("1").value
    id_2 = db.id_intern("2").value
    v1 = db.val_intern("a@b.com").value
    v2 = db.val_intern("+7123").value

    _insert(db, src, lb_a, id_1, v1, act, dt=_TS)
    _insert(db, src, lb_b, id_2, v2, act, dt=_TS)

    result = db.txn_last_values(src, [lb_a, lb_b], [id_1, id_2])
    assert isinstance(result, Ok)
    assert result.value[(lb_a, id_1)] == v1
    assert result.value[(lb_b, id_2)] == v2
    assert (lb_b, id_1) not in result.value
    assert (lb_a, id_2) not in result.value
