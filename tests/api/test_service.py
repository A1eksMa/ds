import json

import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.api import service
from src.config.models import LabelConfig, SourceConfig
from src.domain.enums import Act
from src.domain.errors import StorageError
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


def test_load_with_patch_act(db):
    data = {"customer_id": ["1"], "email": ["v1@b.com"]}
    service.load(db, data, _cfg(), _TS)
    data2 = {"customer_id": ["1"], "email": ["v2@b.com"]}
    result = service.load(db, data2, _cfg(), _TS + 1, act=Act.PATCH)
    assert isinstance(result, Ok)


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
