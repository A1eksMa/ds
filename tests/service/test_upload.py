import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.config.models import LabelConfig, SourceConfig
from src.domain.result import Err, Ok
from src.service import load as svc_load
from src.service import upload as svc_upload

_T1 = 1_700_000_000.0


def _cfg(labels=None, key_label="customer_id", name="CRM"):
    return SourceConfig(name=name, key_label=key_label, labels=dict(labels or {}))


@pytest.fixture
def db():
    return InMemoryAdapter()


# --- unknown label ----------------------------------------------------------

def test_rejects_unknown_label_on_a_never_loaded_source(db):
    data = {"customer_id": ["1"], "email": ["a@e.com"]}
    r = svc_upload.validate_known_schema(db, data, _cfg())
    assert isinstance(r, Err)
    assert r.error.field == "email"


def test_accepts_label_already_known_from_a_previous_load(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    # second batch, config still doesn't declare "email" -- but it's known from the DB now
    data = {"customer_id": ["2"], "email": ["b@e.com"]}
    r = svc_upload.validate_known_schema(db, data, _cfg())
    assert isinstance(r, Ok)


def test_rejects_new_label_even_when_source_already_has_other_known_labels(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    data = {"customer_id": ["2"], "email": ["b@e.com"], "phone": ["+1"]}
    r = svc_upload.validate_known_schema(db, data, _cfg())
    assert isinstance(r, Err)
    assert r.error.field == "phone"


def test_accepts_label_declared_in_source_json_even_on_a_brand_new_source(db):
    cfg = _cfg({"email": LabelConfig(name="email")})  # never loaded, only declared
    data = {"customer_id": ["1"], "email": ["a@e.com"]}
    r = svc_upload.validate_known_schema(db, data, cfg)
    assert isinstance(r, Ok)


def test_key_label_is_never_checked(db):
    # source never loaded, customer_id not declared anywhere -- must not be flagged
    cfg = _cfg({"email": LabelConfig(name="email")})
    data = {"customer_id": ["1"], "email": ["a@e.com"]}
    r = svc_upload.validate_known_schema(db, data, cfg)
    assert isinstance(r, Ok)


# --- type checking ------------------------------------------------------------

def test_number_type_rejects_unparseable_value(db):
    cfg = _cfg({"revenue": LabelConfig(name="revenue", type="number")})
    data = {"customer_id": ["1"], "revenue": ["not-a-number"]}
    r = svc_upload.validate_known_schema(db, cfg=cfg, data=data)
    assert isinstance(r, Err)
    assert r.error.field == "revenue"


def test_number_type_accepts_valid_values(db):
    cfg = _cfg({"revenue": LabelConfig(name="revenue", type="number")})
    data = {"customer_id": ["1", "2"], "revenue": ["100", "-3.5"]}
    r = svc_upload.validate_known_schema(db, data, cfg)
    assert isinstance(r, Ok)


def test_date_type_accepts_iso_and_unix_timestamp(db):
    cfg = _cfg({"signup": LabelConfig(name="signup", type="date")})
    data = {"customer_id": ["1", "2"], "signup": ["2024-02-01", "1706745600"]}
    r = svc_upload.validate_known_schema(db, data, cfg)
    assert isinstance(r, Ok)


def test_date_type_rejects_garbage(db):
    cfg = _cfg({"signup": LabelConfig(name="signup", type="date")})
    data = {"customer_id": ["1"], "signup": ["not-a-date"]}
    r = svc_upload.validate_known_schema(db, data, cfg)
    assert isinstance(r, Err)
    assert r.error.field == "signup"


@pytest.mark.parametrize("value", ["true", "false", "1", "0", "yes", "no", "Y", "N"])
def test_bool_type_accepts_known_tokens(db, value):
    cfg = _cfg({"active": LabelConfig(name="active", type="bool")})
    data = {"customer_id": ["1"], "active": [value]}
    r = svc_upload.validate_known_schema(db, data, cfg)
    assert isinstance(r, Ok)


def test_bool_type_rejects_unknown_token(db):
    cfg = _cfg({"active": LabelConfig(name="active", type="bool")})
    data = {"customer_id": ["1"], "active": ["maybe"]}
    r = svc_upload.validate_known_schema(db, data, cfg)
    assert isinstance(r, Err)
    assert r.error.field == "active"


def test_null_value_is_always_valid_regardless_of_type(db):
    cfg = _cfg({"revenue": LabelConfig(name="revenue", type="number")})
    data = {"customer_id": ["1"], "revenue": [None]}
    r = svc_upload.validate_known_schema(db, data, cfg)
    assert isinstance(r, Ok)


def test_label_known_only_from_db_has_no_type_constraint(db):
    # loaded once as plain text data -- upload later doesn't know it was ever "number"
    svc_load.load(db, {"customer_id": ["1"], "revenue": ["100"]}, _cfg(), _T1)
    data = {"customer_id": ["2"], "revenue": ["definitely not a number"]}
    r = svc_upload.validate_known_schema(db, data, _cfg())  # not declared in source.json
    assert isinstance(r, Ok)
