import json

import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import NotFound, ValidationError
from src.domain.result import Err, Ok
from src.service import get as svc_get
from src.service import load as svc_load

_T1 = 1_700_000_000.0        # "january"
_T2 = 1_700_100_000.0        # "february"
_NOW = 1_700_200_000.0


def _cfg(name="CRM", key_label="customer_id"):
    return SourceConfig(
        name=name, key_label=key_label, p=0.5,
        labels={key_label: LabelConfig(name=key_label)},
    )


@pytest.fixture
def db():
    return InMemoryAdapter()


@pytest.fixture
def crm(db):
    """CRM with two batches, mirroring examples/01-basic-load."""
    svc_load.load(db, {
        "customer_id": ["101", "102", "103"],
        "email": ["alice@e.com", "bob@e.com", "carol@e.com"],
        "phone": ["+1", "+2", None],
    }, _cfg(), _T1)
    svc_load.load(db, {
        "customer_id": ["102", "104"],
        "email": ["bob.new@e.com", "dave@e.com"],
    }, _cfg(), _T2)
    return db


# --- run_get: basic shape ---------------------------------------------------

def test_get_all_sources_all_labels(crm):
    r = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW)
    assert isinstance(r, Ok)
    assert set(r.value) == {"CRM"}
    payload = r.value["CRM"]
    assert payload["meta"]["name"] == "CRM"
    assert payload["meta"]["key"] == "customer_id"
    assert payload["meta"]["as_of"] == _NOW          # dt=None -> now
    assert payload["meta"]["generated_at"] == _NOW
    assert payload["meta"]["labels"] == ["email", "phone"]
    assert payload["meta"]["rows"] == 4


def test_get_rows_are_wide_and_sorted_by_key(crm):
    data = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW).value["CRM"]["data"]
    assert [row["customer_id"] for row in data] == ["101", "102", "103", "104"]


def test_get_post_wins_over_earlier_patch(crm):
    data = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW).value["CRM"]["data"]
    row102 = next(r for r in data if r["customer_id"] == "102")
    assert row102["email"] == "bob.new@e.com"       # second batch won


def test_get_delete_becomes_null(crm):
    data = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW).value["CRM"]["data"]
    row103 = next(r for r in data if r["customer_id"] == "103")
    assert row103["phone"] is None                  # deleted in first batch


def test_get_absent_pair_is_missing_key_not_null(crm):
    data = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW).value["CRM"]["data"]
    row104 = next(r for r in data if r["customer_id"] == "104")
    assert "phone" not in row104                     # 104 never had a phone txn


# --- time machine ---------------------------------------------------------

def test_get_as_of_first_batch(crm):
    r = svc_get.run_get(crm, svc_get.GetParams(dt=_T1), now=_NOW)
    data = r.value["CRM"]["data"]
    assert [row["customer_id"] for row in data] == ["101", "102", "103"]  # 104 not yet
    row102 = next(r for r in data if r["customer_id"] == "102")
    assert row102["email"] == "bob@e.com"           # pre-POST value
    assert r.value["CRM"]["meta"]["as_of"] == _T1


# --- label selection ----------------------------------------------------

def test_get_label_whitelist(crm):
    r = svc_get.run_get(crm, svc_get.GetParams(labels=["email"]), now=_NOW)
    payload = r.value["CRM"]
    assert payload["meta"]["labels"] == ["email"]
    assert all("phone" not in row for row in payload["data"])


def test_get_unknown_label_is_not_found(crm):
    r = svc_get.run_get(crm, svc_get.GetParams(labels=["nope"]), now=_NOW)
    assert isinstance(r, Err) and isinstance(r.error, NotFound)
    assert r.error.entity == "Label" and r.error.key == "CRM.nope"


def test_get_unknown_source_is_not_found(crm):
    r = svc_get.run_get(crm, svc_get.GetParams(sources=["ERP"]), now=_NOW)
    assert isinstance(r, Err) and isinstance(r.error, NotFound)
    assert r.error.entity == "Source" and r.error.key == "ERP"


def test_get_key_label_in_whitelist_is_ignored(crm):
    r = svc_get.run_get(crm, svc_get.GetParams(labels=["customer_id", "email"]), now=_NOW)
    assert r.value["CRM"]["meta"]["labels"] == ["email"]


# --- gen_max_cnt -------------------------------------------------------

def test_get_gen_max_cnt_tracks_slice(crm):
    full = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW).value["CRM"]
    sliced = svc_get.run_get(crm, svc_get.GetParams(dt=_T1), now=_NOW).value["CRM"]
    assert full["meta"]["gen_max_cnt"] == 8          # both batches: 6 + 2
    assert sliced["meta"]["gen_max_cnt"] == 6        # first batch only


# --- fold order: (dt, cnt), not cnt alone ----------------------------------

def test_fold_earlier_dt_later_cnt_does_not_win(db):
    # cnt 1 has the later dt; cnt 2 (loaded after) has an earlier dt.
    svc_load.load(db, {"customer_id": ["1"], "email": ["late-dt"]}, _cfg(), _T2)
    svc_load.load(db, {"customer_id": ["1"], "email": ["early-dt"]}, _cfg(), _T1)
    data = svc_get.run_get(db, svc_get.GetParams(), now=_NOW).value["CRM"]["data"]
    assert data[0]["email"] == "late-dt"             # greater dt wins despite lower cnt


def test_fold_equal_dt_later_cnt_wins(db):
    svc_load.load(db, {"customer_id": ["1"], "email": ["first"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["1"], "email": ["second"]}, _cfg(), _T1)
    data = svc_get.run_get(db, svc_get.GetParams(), now=_NOW).value["CRM"]["data"]
    assert data[0]["email"] == "second"             # same dt -> greater cnt wins


# --- archive ---------------------------------------------------------

def test_get_excludes_archive_by_default(crm):
    crm.txn_archive(until_dt=_T1)                     # first batch -> archive
    payload = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW).value["CRM"]
    ids = {row["customer_id"] for row in payload["data"]}
    assert ids == {"102", "104"}                      # only the un-archived second batch


def test_get_include_archive(crm):
    crm.txn_archive(until_dt=_T1)
    payload = svc_get.run_get(
        crm, svc_get.GetParams(include_archive=True), now=_NOW,
    ).value["CRM"]
    ids = {row["customer_id"] for row in payload["data"]}
    assert ids == {"101", "102", "103", "104"}


# --- preset loading + overrides -------------------------------------------

def test_load_preset_query_section(tmp_path):
    p = tmp_path / "preset.json"
    p.write_text(json.dumps({
        "name": "base",
        "query": {
            "as_of": 1234.0,
            "include_archive": True,
            "sources": {"CRM": {"labels": ["email", "phone"]}, "ERP": {"labels": ["price"]}},
        },
        "view": {"joins": [{"left": "CRM", "right": "ERP"}]},
    }), encoding="utf-8")

    r = svc_get.load_preset(p)
    assert isinstance(r, Ok)
    params = r.value
    assert params.sources == ["CRM", "ERP"]
    assert params.labels_by_source == {"CRM": ["email", "phone"], "ERP": ["price"]}
    assert params.dt == 1234.0
    assert params.include_archive is True


def test_load_preset_sources_as_array(tmp_path):
    p = tmp_path / "preset.json"
    p.write_text(json.dumps({"query": {"sources": ["CRM"]}}), encoding="utf-8")
    r = svc_get.load_preset(p)
    assert isinstance(r, Ok)
    assert r.value.sources == ["CRM"]
    assert r.value.labels_by_source == {}


def test_load_preset_bad_sources_type(tmp_path):
    p = tmp_path / "preset.json"
    p.write_text(json.dumps({"query": {"sources": 5}}), encoding="utf-8")
    r = svc_get.load_preset(p)
    assert isinstance(r, Err) and isinstance(r.error, ValidationError)


def test_merge_overrides_cli_wins():
    base = svc_get.GetParams(
        sources=["CRM", "ERP"],
        labels_by_source={"CRM": ["email"]},
        labels=None, dt=100.0, include_archive=False,
    )
    merged = svc_get.merge_overrides(
        base, src_names=["CRM"], lb_names=["phone"], dt=999.0, include_archive=True,
    )
    assert merged.sources == ["CRM"]
    assert merged.labels == ["phone"]
    assert merged.labels_by_source == {}             # global --lb drops per-source
    assert merged.dt == 999.0
    assert merged.include_archive is True


def test_merge_overrides_archive_only_turns_on():
    base = svc_get.GetParams(include_archive=True)
    merged = svc_get.merge_overrides(base, include_archive=False)
    assert merged.include_archive is True            # preset's True is kept


def test_preset_drives_get_end_to_end(crm, tmp_path):
    p = tmp_path / "preset.json"
    p.write_text(json.dumps({
        "query": {"as_of": _T1, "sources": {"CRM": {"labels": ["email"]}}},
    }), encoding="utf-8")
    params = svc_get.load_preset(p).value
    r = svc_get.run_get(crm, params, now=_NOW)
    payload = r.value["CRM"]
    assert payload["meta"]["as_of"] == _T1
    assert payload["meta"]["labels"] == ["email"]
    assert [row["customer_id"] for row in payload["data"]] == ["101", "102", "103"]
