import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.domain.entities import ActId, IdId, LbId, Src, SrcId, TransactionInput, ValId
from src.domain.enums import Act
from src.domain.errors import StorageError
from src.domain.result import Err, Ok

_TS = 1_700_000_000.0


@pytest.fixture
def db() -> InMemoryAdapter:
    return InMemoryAdapter()


# --- String pool operations ---

def test_lb_intern_creates_entry(db):
    result = db.lb_intern("email")
    assert isinstance(result, Ok)
    assert isinstance(result.value, int)


def test_lb_intern_returns_same_id_on_repeat(db):
    first = db.lb_intern("email").value
    second = db.lb_intern("email").value
    assert first == second


def test_lb_intern_different_names_get_different_ids(db):
    a = db.lb_intern("email").value
    b = db.lb_intern("phone").value
    assert a != b


def test_id_intern_creates_entry(db):
    result = db.id_intern("42")
    assert isinstance(result, Ok)


def test_id_intern_same_value_same_id(db):
    assert db.id_intern("42").value == db.id_intern("42").value


def test_val_intern_creates_entry(db):
    result = db.val_intern("alice@example.com")
    assert isinstance(result, Ok)


def test_val_intern_same_value_same_id(db):
    assert db.val_intern("x").value == db.val_intern("x").value


def test_act_intern_all_variants(db):
    for act in Act:
        result = db.act_intern(act)
        assert isinstance(result, Ok)


def test_act_intern_same_act_same_id(db):
    a = db.act_intern(Act.POST).value
    b = db.act_intern(Act.POST).value
    assert a == b


def test_act_intern_different_acts_get_different_ids(db):
    post = db.act_intern(Act.POST).value
    delete = db.act_intern(Act.DELETE).value
    assert post != delete


# --- Source metadata ---

def test_src_get_or_create_creates_source(db):
    lb_id = db.lb_intern("customer_id").value
    result = db.src_get_or_create("CRM", lb_id)
    assert isinstance(result, Ok)
    src = result.value
    assert src.name == "CRM"
    assert src.key_label == lb_id
    assert src.p == 0.5


def test_src_get_or_create_idempotent(db):
    lb_id = db.lb_intern("customer_id").value
    first = db.src_get_or_create("CRM", lb_id).value
    second = db.src_get_or_create("CRM", lb_id).value
    assert first.src_id == second.src_id


def test_src_get_not_found(db):
    result = db.src_get(SrcId(999))
    assert isinstance(result, Err)
    assert isinstance(result.error, StorageError)


def test_src_update_changes_p_and_description(db):
    lb_id = db.lb_intern("id").value
    src = db.src_get_or_create("ERP", lb_id).value
    updated = Src(src_id=src.src_id, name=src.name, p=0.95, key_label=src.key_label, description="ERP system")
    db.src_update(updated)
    refreshed = db.src_get(src.src_id).value
    assert refreshed.p == 0.95
    assert refreshed.description == "ERP system"


def test_src_list_returns_all_sources(db):
    lb_id = db.lb_intern("id").value
    db.src_get_or_create("CRM", lb_id)
    db.src_get_or_create("ERP", lb_id)
    result = db.src_list()
    assert isinstance(result, Ok)
    names = {s.name for s in result.value}
    assert names == {"CRM", "ERP"}


# --- Label metadata ---

def test_lb_get_returns_label(db):
    lb_id = db.lb_intern("email").value
    result = db.lb_get(lb_id)
    assert isinstance(result, Ok)
    assert result.value.name == "email"


def test_lb_get_not_found(db):
    result = db.lb_get(LbId(999))
    assert isinstance(result, Err)


def test_lb_update_changes_p_and_description(db):
    from src.domain.entities import Lb
    lb_id = db.lb_intern("price").value
    lb = db.lb_get(lb_id).value
    updated = Lb(lb_id=lb.lb_id, name=lb.name, p=0.95, description="Unit price")
    db.lb_update(updated)
    refreshed = db.lb_get(lb_id).value
    assert refreshed.p == 0.95
    assert refreshed.description == "Unit price"


def test_lb_list_returns_all_labels(db):
    db.lb_intern("email")
    db.lb_intern("phone")
    result = db.lb_list()
    assert isinstance(result, Ok)
    names = {lb.name for lb in result.value}
    assert {"email", "phone"}.issubset(names)


# --- Transactions ---

def _insert(db, src_id, lb_id, id_id, val_id, act_id, dt=_TS, p=1.0):
    return db.txn_insert(TransactionInput(
        act=act_id, dt=dt, src=src_id,
        lb=lb_id, id=id_id, p=p, val=val_id,
    ))


def test_txn_insert_returns_transaction_with_cnt(db):
    lb_id = db.lb_intern("email").value
    src_id = db.src_get_or_create("CRM", lb_id).value.src_id
    act_id = db.act_intern(Act.POST).value
    id_id = db.id_intern("1").value
    val_id = db.val_intern("a@b.com").value

    result = _insert(db, src_id, lb_id, id_id, val_id, act_id)
    assert isinstance(result, Ok)
    txn = result.value
    assert txn.cnt is not None
    assert txn.src == src_id
    assert txn.lb == lb_id
    assert txn.val == val_id


def test_txn_insert_increments_cnt(db):
    lb_id = db.lb_intern("x").value
    src_id = db.src_get_or_create("S", lb_id).value.src_id
    act_id = db.act_intern(Act.POST).value
    id_id = db.id_intern("1").value
    val_id = db.val_intern("v").value

    t1 = _insert(db, src_id, lb_id, id_id, val_id, act_id).value
    t2 = _insert(db, src_id, lb_id, id_id, val_id, act_id).value
    assert t2.cnt > t1.cnt


def test_txn_query_returns_all(db):
    lb_id = db.lb_intern("x").value
    src_id = db.src_get_or_create("S", lb_id).value.src_id
    act_id = db.act_intern(Act.POST).value
    id_id = db.id_intern("1").value
    val_id = db.val_intern("v").value

    _insert(db, src_id, lb_id, id_id, val_id, act_id, dt=_TS)
    _insert(db, src_id, lb_id, id_id, val_id, act_id, dt=_TS + 1)

    result = db.txn_query()
    assert isinstance(result, Ok)
    assert len(result.value) == 2


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
    assert all(t.src == src_a for t in result.value)
    assert len(result.value) == 1


def test_txn_query_filters_by_until_dt(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    _insert(db, src, lb, id_, val, act, dt=_TS + 100)

    result = db.txn_query(until_dt=_TS + 50)
    assert isinstance(result, Ok)
    assert len(result.value) == 1
    assert result.value[0].dt == _TS


def test_txn_query_filters_by_from_cnt(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    t1 = _insert(db, src, lb, id_, val, act).value
    _insert(db, src, lb, id_, val, act)
    _insert(db, src, lb, id_, val, act)

    result = db.txn_query(from_cnt=t1.cnt)
    assert isinstance(result, Ok)
    assert len(result.value) == 2
    assert all(t.cnt > t1.cnt for t in result.value)


def test_txn_query_val_none_delete_semantics(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.DELETE).value
    id_ = db.id_intern("1").value

    db.txn_insert(TransactionInput(act=act, dt=_TS, src=src, lb=lb, id=id_, p=1.0, val=ValId(0)))
    result = db.txn_query()
    assert isinstance(result, Ok)
    assert result.value[0].val == ValId(0)


def test_txn_archive_moves_records(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    _insert(db, src, lb, id_, val, act, dt=_TS + 100)

    arch_result = db.txn_archive(until_dt=_TS + 50)
    assert isinstance(arch_result, Ok)
    assert arch_result.value == 1

    active = db.txn_query().value
    assert len(active) == 1
    assert active[0].dt == _TS + 100

    with_archive = db.txn_query(include_archive=True).value
    assert len(with_archive) == 2


def test_txn_delete_by_src(db):
    lb = db.lb_intern("x").value
    src = db.src_get_or_create("S", lb).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act)
    _insert(db, src, lb, id_, val, act)
    db.txn_delete(src_id=src)

    assert db.txn_query().value == []


def test_txn_delete_by_src_and_lb(db):
    lb_a = db.lb_intern("a").value
    lb_b = db.lb_intern("b").value
    src = db.src_get_or_create("S", lb_a).value.src_id
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb_a, id_, val, act)
    _insert(db, src, lb_b, id_, val, act)

    db.txn_delete(src_id=src, lb_id=lb_a)

    remaining = db.txn_query().value
    assert len(remaining) == 1
    assert remaining[0].lb == lb_b


