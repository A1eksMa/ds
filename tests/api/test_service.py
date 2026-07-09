import json

import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.api import service
from src.config.models import LabelConfig, SourceConfig
from src.domain.entities import TransactionInput, ValId
from src.domain.enums import Act
from src.domain.errors import NotFound, StorageError
from src.domain.result import Err, Ok

_TS = 1_700_000_000.0


def _cfg(key="customer_id", name="CRM"):
    return SourceConfig(
        name=name, key_label=key, p=0.9,
        labels={key: LabelConfig(name=key)},
    )


@pytest.fixture
def db():
    return InMemoryAdapter()


# --- load ---

def test_load_returns_transaction_count(db):
    data = {"customer_id": ["1", "2"], "email": ["a@b.com", "b@b.com"]}
    result = service.load(db, data, _cfg(), _TS)
    assert isinstance(result, Ok)
    assert result.value == 2


def test_load_returns_err_on_validation_failure(db):
    data = {"wrong_col": ["1"]}
    result = service.load(db, data, _cfg(), _TS)
    assert isinstance(result, Err)


def test_load_overwriting_existing_value_is_post(db):
    data = {"customer_id": ["1"], "email": ["v1@b.com"]}
    service.load(db, data, _cfg(), _TS)
    data2 = {"customer_id": ["1"], "email": ["v2@b.com"]}
    service.load(db, data2, _cfg(), _TS + 1)
    txns = db.txn_query().value
    assert txns[-1].act == db.act_intern(Act.POST).value


def test_load_multiple_batches_accumulate_transactions(db):
    data1 = {"customer_id": ["1"], "email": ["a@b.com"]}
    service.load(db, data1, _cfg(), _TS)
    data2 = {"customer_id": ["2"], "email": ["b@b.com"]}
    service.load(db, data2, _cfg(), _TS + 1)
    txns = db.txn_query()
    assert isinstance(txns, Ok)
    assert len(txns.value) == 2


# --- load_file ---

def test_load_file_valid(db, tmp_path):
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    f = tmp_path / "data.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    result = service.load_file(db, f, _cfg(), _TS)
    assert isinstance(result, Ok)
    assert result.value == 1


def test_load_file_not_found(db, tmp_path):
    result = service.load_file(db, tmp_path / "missing.json", _cfg(), _TS)
    assert isinstance(result, Err)
    assert isinstance(result.error, StorageError)


def test_load_file_invalid_json(db, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not valid {{", encoding="utf-8")
    result = service.load_file(db, f, _cfg(), _TS)
    assert isinstance(result, Err)


# --- build_export ---

def test_build_export_empty_storage_returns_empty_data(db):
    result = service.build_export(db, generated_at=_TS)
    assert isinstance(result, Ok)
    assert result.value["data"] == []
    assert result.value["metadata"]["count"] == 0


def test_build_export_resolves_names(db):
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    service.load(db, data, _cfg(), _TS)

    result = service.build_export(db, generated_at=_TS + 100)
    assert isinstance(result, Ok)
    assert result.value["data"] == [
        {"src": "CRM", "lb": "email", "id": "1", "val": "a@b.com"}
    ]
    assert result.value["metadata"] == {
        "generated_at": _TS + 100,
        "until_dt": None,
        "include_archive": False,
        "src": None,
        "lb": None,
        "count": 1,
    }


def test_build_export_delete_is_null_val(db):
    data = {"customer_id": ["1"], "email": ["a@b.com"]}
    service.load(db, data, _cfg(), _TS)
    data2 = {"customer_id": ["1"], "email": [None]}
    service.load(db, data2, _cfg(), _TS + 1)

    result = service.build_export(db, generated_at=_TS + 100)
    assert isinstance(result, Ok)
    assert result.value["data"] == [
        {"src": "CRM", "lb": "email", "id": "1", "val": None}
    ]


def test_build_export_filters_by_src_name(db):
    service.load(db, {"customer_id": ["1"], "email": ["a@b.com"]}, _cfg(name="CRM"), _TS)
    service.load(db, {"customer_id": ["1"], "email": ["b@b.com"]}, _cfg(name="ERP"), _TS)

    result = service.build_export(db, generated_at=_TS + 100, src_name="ERP")
    assert isinstance(result, Ok)
    assert result.value["data"] == [
        {"src": "ERP", "lb": "email", "id": "1", "val": "b@b.com"}
    ]
    assert result.value["metadata"]["src"] == "ERP"


def test_build_export_unknown_src_name_returns_not_found(db):
    result = service.build_export(db, generated_at=_TS, src_name="does-not-exist")
    assert isinstance(result, Err)
    assert result.error == NotFound(entity="Src", key="does-not-exist")


def test_build_export_unknown_lb_name_returns_not_found(db):
    service.load(db, {"customer_id": ["1"], "email": ["a@b.com"]}, _cfg(), _TS)
    result = service.build_export(db, generated_at=_TS, lb_name="does-not-exist")
    assert isinstance(result, Err)
    assert result.error == NotFound(entity="Lb", key="does-not-exist")


def test_build_export_until_dt_reconstructs_past_snapshot(db):
    lb = db.lb_intern("email").value
    src = db.src_get_or_create("CRM", lb).value.src_id
    id_ = db.id_intern("1").value
    post = db.act_intern(Act.POST).value
    patch = db.act_intern(Act.PATCH).value
    v1 = db.val_intern("v1@b.com").value
    v2 = db.val_intern("v2@b.com").value
    db.txn_insert(TransactionInput(act=post, dt=_TS, src=src, lb=lb, id=id_, p=1.0, val=v1))
    db.txn_insert(TransactionInput(act=patch, dt=_TS + 10, src=src, lb=lb, id=id_, p=1.0, val=v2))

    result = service.build_export(db, generated_at=_TS + 100, until_dt=_TS)
    assert isinstance(result, Ok)
    assert result.value["data"] == [
        {"src": "CRM", "lb": "email", "id": "1", "val": "v1@b.com"}
    ]
    assert result.value["metadata"]["until_dt"] == _TS


# --- export_state_file ---

def test_export_state_file_writes_json(db, tmp_path):
    service.load(db, {"customer_id": ["1"], "email": ["a@b.com"]}, _cfg(), _TS)
    out = tmp_path / "state.json"

    result = service.export_state_file(db, out, generated_at=_TS + 100)
    assert isinstance(result, Ok)
    assert result.value == 1

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["data"] == [
        {"src": "CRM", "lb": "email", "id": "1", "val": "a@b.com"}
    ]
    assert written["metadata"]["count"] == 1


def test_export_state_file_unknown_src_does_not_write_file(db, tmp_path):
    out = tmp_path / "state.json"
    result = service.export_state_file(db, out, generated_at=_TS, src_name="nope")
    assert isinstance(result, Err)
    assert not out.exists()
