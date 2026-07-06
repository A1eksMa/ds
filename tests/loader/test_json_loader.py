import json

import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.config.models import LabelConfig, SourceConfig
from src.domain.entities import ValId
from src.domain.enums import Act
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok
from src.loader import json_loader

_TS = 1_700_000_000.0


def _cfg(key_label="customer_id", name="CRM", p=0.9):
    return SourceConfig(
        name=name, key_label=key_label, p=p,
        labels={key_label: LabelConfig(name=key_label)},
    )


@pytest.fixture
def db():
    return InMemoryAdapter()


# --- подсчёт транзакций ---

def test_load_one_row_one_column(db):
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    result = json_loader.load(db, data, _cfg(), _TS)
    assert isinstance(result, Ok)
    assert result.value == 1  # 1 строка × 1 не-ключевой столбец


def test_load_multiple_rows(db):
    data = {"customer_id": ["1", "2", "3"], "email": ["a", "b", "c"]}
    result = json_loader.load(db, data, _cfg(), _TS)
    assert isinstance(result, Ok)
    assert result.value == 3


def test_load_multiple_columns(db):
    data = {"customer_id": ["1"], "email": ["a@b.com"], "phone": ["+7123"]}
    result = json_loader.load(db, data, _cfg(), _TS)
    assert isinstance(result, Ok)
    assert result.value == 2  # 1 строка × 2 не-ключевых столбца


def test_load_empty_table(db):
    data = {"customer_id": [], "email": []}
    result = json_loader.load(db, data, _cfg(), _TS)
    assert isinstance(result, Ok)
    assert result.value == 0


# --- транзакции в хранилище ---

def test_load_inserts_transactions(db):
    data = {"customer_id": ["1", "2"], "email": ["a@b.com", "b@b.com"]}
    json_loader.load(db, data, _cfg(), _TS)
    assert len(db.txn_query().value) == 2


def test_load_creates_source(db):
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    json_loader.load(db, data, _cfg(), _TS)
    assert any(s.name == "CRM" for s in db.src_list().value)


def test_load_creates_labels(db):
    data = {"customer_id": ["1"], "email": ["a@b.com"], "phone": ["+7"]}
    json_loader.load(db, data, _cfg(), _TS)
    names = {lb.name for lb in db.lb_list().value}
    assert {"customer_id", "email", "phone"}.issubset(names)


def test_load_idempotent_source_creation(db):
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    json_loader.load(db, data, _cfg(), _TS)
    json_loader.load(db, data, _cfg(), _TS + 1)
    assert len([s for s in db.src_list().value if s.name == "CRM"]) == 1


# --- семантика значений ---

def test_load_null_value_produces_val_zero(db):
    data = {"customer_id": ["1"], "email": [None]}
    json_loader.load(db, data, _cfg(), _TS)
    assert db.txn_query().value[0].val == ValId(0)


def test_load_int_values_converted_to_string(db):
    data = {"customer_id": [1, 2], "score": [95, 87]}
    result = json_loader.load(db, data, _cfg(), _TS)
    assert isinstance(result, Ok)
    assert result.value == 2


def test_load_float_values_converted_to_string(db):
    data = {"customer_id": ["1"], "price": [99.99]}
    result = json_loader.load(db, data, _cfg(), _TS)
    assert isinstance(result, Ok)


# --- act auto-detection ---

def test_load_first_insert_is_patch(db):
    """No prior record for (lb, id) -> PATCH."""
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    json_loader.load(db, data, _cfg(), _TS)
    txn = db.txn_query().value[0]
    assert txn.act == db.act_intern(Act.PATCH).value


def test_load_overwriting_existing_value_is_post(db):
    """Prior record had a value -> POST."""
    data1 = {"customer_id": ["1"], "email": ["a@b.com"]}
    json_loader.load(db, data1, _cfg(), _TS)
    data2 = {"customer_id": ["1"], "email": ["b@b.com"]}
    json_loader.load(db, data2, _cfg(), _TS + 1)

    txns = db.txn_query().value
    assert txns[-1].act == db.act_intern(Act.POST).value


def test_load_null_value_is_delete(db):
    """Null value -> DELETE, regardless of prior history."""
    data = {"customer_id": ["1"], "email": [None]}
    json_loader.load(db, data, _cfg(), _TS)
    txn = db.txn_query().value[0]
    assert txn.act == db.act_intern(Act.DELETE).value


def test_load_after_delete_is_patch_again(db):
    """Prior record was deleted (val=0) -> PATCH, not POST."""
    data1 = {"customer_id": ["1"], "email": ["a@b.com"]}
    json_loader.load(db, data1, _cfg(), _TS)
    data2 = {"customer_id": ["1"], "email": [None]}
    json_loader.load(db, data2, _cfg(), _TS + 1)
    data3 = {"customer_id": ["1"], "email": ["c@b.com"]}
    json_loader.load(db, data3, _cfg(), _TS + 2)

    txns = db.txn_query().value
    assert txns[-1].act == db.act_intern(Act.PATCH).value


def test_load_considers_archived_history(db):
    """History check must include archived transactions, not just active ones."""
    data1 = {"customer_id": ["1"], "email": ["a@b.com"]}
    json_loader.load(db, data1, _cfg(), _TS)
    db.txn_archive(until_dt=_TS + 1)  # first record now archived, not active

    data2 = {"customer_id": ["1"], "email": ["b@b.com"]}
    json_loader.load(db, data2, _cfg(), _TS + 100)

    txns = db.txn_query(include_archive=True).value
    assert txns[-1].act == db.act_intern(Act.POST).value


def test_load_independent_ids_get_independent_act(db):
    """Each (lb, id) pair is judged on its own history within the same batch."""
    data1 = {"customer_id": ["1"], "email": ["a@b.com"]}
    json_loader.load(db, data1, _cfg(), _TS)

    data2 = {"customer_id": ["1", "2"], "email": ["updated@b.com", "new@b.com"]}
    json_loader.load(db, data2, _cfg(), _TS + 1)

    id1 = db.id_intern("1").value
    id2 = db.id_intern("2").value
    latest = {t.id: t for t in db.txn_query().value if t.dt == _TS + 1}
    assert latest[id1].act == db.act_intern(Act.POST).value
    assert latest[id2].act == db.act_intern(Act.PATCH).value


def test_load_timestamp_stored_in_transactions(db):
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    json_loader.load(db, data, _cfg(), _TS)
    assert db.txn_query().value[0].dt == _TS


# --- ошибки валидации ---

def test_load_validation_error_no_key_label(db):
    data = {"wrong_col": ["1"]}
    result = json_loader.load(db, data, _cfg(), _TS)
    assert isinstance(result, Err)
    assert isinstance(result.error, ValidationError)


def test_load_validation_error_propagates_no_transactions(db):
    data = {"wrong_col": ["1"]}
    json_loader.load(db, data, _cfg(), _TS)
    assert db.txn_query().value == []


# --- load_file ---

def test_load_file_valid(db, tmp_path):
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    f = tmp_path / "data.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    result = json_loader.load_file(db, f, _cfg(), _TS)
    assert isinstance(result, Ok)
    assert result.value == 1


def test_load_file_not_found(db, tmp_path):
    result = json_loader.load_file(db, tmp_path / "missing.json", _cfg(), _TS)
    assert isinstance(result, Err)


def test_load_file_invalid_json(db, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not valid json {{", encoding="utf-8")
    result = json_loader.load_file(db, f, _cfg(), _TS)
    assert isinstance(result, Err)
