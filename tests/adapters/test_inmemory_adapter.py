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


def _src(db, name="S") -> SrcId:
    return db.src_get_or_create(name).value.src_id


# --- String pool operations ---

def test_lb_intern_creates_entry(db):
    src = _src(db)
    result = db.lb_intern("email", src)
    assert isinstance(result, Ok)
    assert isinstance(result.value, int)


def test_lb_intern_returns_same_id_on_repeat(db):
    src = _src(db)
    first = db.lb_intern("email", src).value
    second = db.lb_intern("email", src).value
    assert first == second


def test_lb_intern_different_names_get_different_ids(db):
    src = _src(db)
    a = db.lb_intern("email", src).value
    b = db.lb_intern("phone", src).value
    assert a != b


def test_lb_intern_same_name_different_sources_get_different_ids(db):
    src_a = _src(db, "A")
    src_b = _src(db, "B")
    a = db.lb_intern("email", src_a).value
    b = db.lb_intern("email", src_b).value
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
    result = db.src_get_or_create("CRM")
    assert isinstance(result, Ok)
    src = result.value
    assert src.name == "CRM"
    assert src.key_label is None
    assert src.p == 0.5


def test_src_get_or_create_idempotent(db):
    first = db.src_get_or_create("CRM").value
    second = db.src_get_or_create("CRM").value
    assert first.src_id == second.src_id


def test_src_get_not_found(db):
    result = db.src_get(SrcId(999))
    assert isinstance(result, Err)
    assert isinstance(result.error, StorageError)


def test_src_set_key_label_bootstraps_key_label(db):
    src = db.src_get_or_create("CRM").value
    lb_id = db.lb_intern("customer_id", src.src_id).value
    result = db.src_set_key_label(src.src_id, lb_id)
    assert isinstance(result, Ok)
    refreshed = db.src_get(src.src_id).value
    assert refreshed.key_label == lb_id


def test_src_update_changes_p_and_description(db):
    src = db.src_get_or_create("ERP").value
    updated = Src(src_id=src.src_id, name=src.name, p=0.95, key_label=src.key_label, description="ERP system")
    db.src_update(updated)
    refreshed = db.src_get(src.src_id).value
    assert refreshed.p == 0.95
    assert refreshed.description == "ERP system"


def test_src_list_returns_all_sources(db):
    db.src_get_or_create("CRM")
    db.src_get_or_create("ERP")
    result = db.src_list()
    assert isinstance(result, Ok)
    names = {s.name for s in result.value}
    assert names == {"CRM", "ERP"}


# --- Label metadata ---

def test_lb_get_returns_label(db):
    src = _src(db)
    lb_id = db.lb_intern("email", src).value
    result = db.lb_get(lb_id)
    assert isinstance(result, Ok)
    assert result.value.name == "email"
    assert result.value.src == src


def test_lb_get_not_found(db):
    result = db.lb_get(LbId(999))
    assert isinstance(result, Err)


def test_lb_update_changes_p_and_description(db):
    from src.domain.entities import Lb
    src = _src(db)
    lb_id = db.lb_intern("price", src).value
    lb = db.lb_get(lb_id).value
    updated = Lb(lb_id=lb.lb_id, name=lb.name, p=0.95, src=lb.src, description="Unit price")
    db.lb_update(updated)
    refreshed = db.lb_get(lb_id).value
    assert refreshed.p == 0.95
    assert refreshed.description == "Unit price"


def test_lb_list_returns_all_labels(db):
    src = _src(db)
    db.lb_intern("email", src)
    db.lb_intern("phone", src)
    result = db.lb_list()
    assert isinstance(result, Ok)
    names = {lb.name for lb in result.value}
    assert {"email", "phone"}.issubset(names)


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
    src_id = _src(db, "CRM")
    lb_id = db.lb_intern("email", src_id).value
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


def test_txn_insert_populates_created_at(db):
    src_id = _src(db, "CRM")
    lb_id = db.lb_intern("email", src_id).value
    act_id = db.act_intern(Act.POST).value
    id_id = db.id_intern("1").value
    val_id = db.val_intern("a@b.com").value

    txn = _insert(db, src_id, lb_id, id_id, val_id, act_id).value
    assert txn.created_at is not None


def test_txn_insert_increments_cnt(db):
    src_id = _src(db)
    lb_id = db.lb_intern("x", src_id).value
    act_id = db.act_intern(Act.POST).value
    id_id = db.id_intern("1").value
    val_id = db.val_intern("v").value

    t1 = _insert(db, src_id, lb_id, id_id, val_id, act_id).value
    t2 = _insert(db, src_id, lb_id, id_id, val_id, act_id).value
    assert t2.cnt > t1.cnt


def test_txn_insert_archived_goes_straight_to_archive(db):
    src_id = _src(db)
    lb_id = db.lb_intern("x", src_id).value
    act_id = db.act_intern(Act.POST).value
    id_id = db.id_intern("1").value
    val_id = db.val_intern("v").value

    result = db.txn_insert(
        TransactionInput(act=act_id, dt=_TS, src=src_id, lb=lb_id, id=id_id, p=1.0, val=val_id),
        archived=True,
    )
    assert isinstance(result, Ok)
    assert db.txn_query().value == []
    assert len(db.txn_query(include_archive=True).value) == 1


def test_txn_query_returns_all(db):
    src_id = _src(db)
    lb_id = db.lb_intern("x", src_id).value
    act_id = db.act_intern(Act.POST).value
    id_id = db.id_intern("1").value
    val_id = db.val_intern("v").value

    _insert(db, src_id, lb_id, id_id, val_id, act_id, dt=_TS)
    _insert(db, src_id, lb_id, id_id, val_id, act_id, dt=_TS + 1)

    result = db.txn_query()
    assert isinstance(result, Ok)
    assert len(result.value) == 2


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
    assert all(t.src == src_a for t in result.value)
    assert len(result.value) == 1


def test_txn_query_filters_by_until_dt(db):
    src = _src(db)
    lb = db.lb_intern("x", src).value
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
    src = _src(db)
    lb = db.lb_intern("x", src).value
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
    src = _src(db)
    lb = db.lb_intern("x", src).value
    act = db.act_intern(Act.DELETE).value
    id_ = db.id_intern("1").value

    db.txn_insert(TransactionInput(act=act, dt=_TS, src=src, lb=lb, id=id_, p=1.0, val=ValId(0)))
    result = db.txn_query()
    assert isinstance(result, Ok)
    assert result.value[0].val == ValId(0)


def test_txn_archive_moves_records(db):
    src = _src(db)
    lb = db.lb_intern("x", src).value
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
    src = _src(db)
    lb = db.lb_intern("x", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act)
    _insert(db, src, lb, id_, val, act)
    result = db.txn_delete(src_id=src)

    assert isinstance(result, Ok)
    assert result.value == 2
    assert db.txn_query().value == []


def test_txn_delete_by_src_and_lb(db):
    src = _src(db)
    lb_a = db.lb_intern("a", src).value
    lb_b = db.lb_intern("b", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb_a, id_, val, act)
    _insert(db, src, lb_b, id_, val, act)

    result = db.txn_delete(src_id=src, lb_ids=[lb_a])

    assert isinstance(result, Ok)
    assert result.value == 1
    remaining = db.txn_query().value
    assert len(remaining) == 1
    assert remaining[0].lb == lb_b


def test_txn_delete_counts_archived_rows_too(db):
    # regression: txn_delete used to report only the active-table rowcount,
    # silently undercounting when matching rows also existed in the archive
    src = _src(db)
    lb = db.lb_intern("x", src).value
    act = db.act_intern(Act.POST).value
    id_ = db.id_intern("1").value
    val = db.val_intern("v").value

    _insert(db, src, lb, id_, val, act, dt=_TS)
    db.txn_archive(until_dt=_TS + 1)
    _insert(db, src, lb, id_, val, act, dt=_TS + 200)

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
