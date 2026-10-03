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


# --- incremental fold cache (`ds get --cache`) -----------------------------

class _CountingAdapter(InMemoryAdapter):
    """Spy on txn_query so a test can tell the fast path (from_cnt set) was
    actually taken, not just that the result happens to be correct."""
    def __init__(self):
        super().__init__()
        self.calls = []

    def txn_query(self, *args, **kwargs):
        self.calls.append(kwargs)
        return super().txn_query(*args, **kwargs)


def test_cached_first_call_matches_plain_run_get(crm):
    cached = svc_get.run_get_cached(crm, svc_get.GetParams(), now=_NOW, cache={})
    plain = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW)
    assert isinstance(cached, Ok)
    payloads, new_cache = cached.value
    assert payloads == plain.value
    assert set(new_cache) == {"CRM"}
    assert new_cache["CRM"].max_cnt == payloads["CRM"]["meta"]["gen_max_cnt"]
    assert new_cache["CRM"].struct_version == 0


def test_cached_second_call_takes_fast_path_and_matches_full_rebuild():
    db = _CountingAdapter()
    svc_load.load(db, {"customer_id": ["1"], "email": ["a@e.com"]}, _cfg(), _T1)
    r1 = svc_get.run_get_cached(db, svc_get.GetParams(), now=_T1 + 1, cache={})
    _, cache1 = r1.value

    db.calls.clear()
    svc_load.load(db, {"customer_id": ["2"], "email": ["b@e.com"]}, _cfg(), _T2)
    r2 = svc_get.run_get_cached(db, svc_get.GetParams(), now=_T2 + 1, cache=cache1)
    assert isinstance(r2, Ok)
    payloads2, cache2 = r2.value

    # fast path: at least one txn_query call used from_cnt (the "what's new" query)
    assert any(c.get("from_cnt") is not None for c in db.calls)

    full = svc_get.run_get(db, svc_get.GetParams(), now=_T2 + 1)
    assert payloads2 == full.value
    assert cache2["CRM"].struct_version == 0


def test_cached_struct_version_change_forces_rebuild_but_stays_correct(crm):
    r1 = svc_get.run_get_cached(crm, svc_get.GetParams(), now=_NOW, cache={})
    _, cache1 = r1.value

    crm.txn_archive(until_dt=_T1)  # structural change -- bumps CRM's struct_version

    r2 = svc_get.run_get_cached(crm, svc_get.GetParams(), now=_NOW, cache=cache1)
    payloads2, cache2 = r2.value
    full = svc_get.run_get(crm, svc_get.GetParams(), now=_NOW)
    assert payloads2 == full.value
    assert cache2["CRM"].struct_version == 1


def test_cached_label_selection_change_forces_rebuild(crm):
    r1 = svc_get.run_get_cached(crm, svc_get.GetParams(labels=["email"]), now=_NOW, cache={})
    _, cache1 = r1.value

    r2 = svc_get.run_get_cached(
        crm, svc_get.GetParams(labels=["email", "phone"]), now=_NOW, cache=cache1,
    )
    payloads2, _ = r2.value
    full = svc_get.run_get(crm, svc_get.GetParams(labels=["email", "phone"]), now=_NOW)
    assert payloads2 == full.value


def test_cached_picks_up_future_dated_row_once_it_comes_into_range():
    # A batch can interleave a "normal" row with a future-dated one; the future
    # row's cnt can be LOWER than other, already-folded rows from a later batch
    # (global cnt order, not per-row dt order) -- see docs/decisions/
    # 0010-incremental-fold-cache.md. A pure "cnt > watermark" catch-up would
    # permanently miss it once its dt finally comes into range.
    db = InMemoryAdapter()
    far_future = _NOW + 10_000
    svc_load.load(db, {"customer_id": ["1"], "email": ["scheduled"]}, _cfg(), far_future)
    svc_load.load(db, {"customer_id": ["2"], "email": ["normal"]}, _cfg(), _T1)

    r1 = svc_get.run_get_cached(db, svc_get.GetParams(), now=_NOW, cache={})
    payloads1, cache1 = r1.value
    ids1 = {row["customer_id"] for row in payloads1["CRM"]["data"]}
    assert ids1 == {"2"}  # future row correctly excluded so far

    r2 = svc_get.run_get_cached(db, svc_get.GetParams(), now=far_future + 1, cache=cache1)
    payloads2, _ = r2.value
    ids2 = {row["customer_id"] for row in payloads2["CRM"]["data"]}
    assert ids2 == {"1", "2"}  # now in range -- must have been picked up

    full = svc_get.run_get(db, svc_get.GetParams(), now=far_future + 1)
    assert payloads2 == full.value


def test_cache_entry_json_round_trip():
    entry = svc_get.SourceCacheEntry(
        struct_version=2, max_cnt=5, as_of=123.0, include_archive=True,
        labels=("email", "phone"), winners={(1, 2): (100.0, 5, 9)},
    )
    restored = svc_get.cache_entry_from_json(svc_get.cache_entry_to_json(entry))
    assert restored == entry


def test_cache_entry_from_json_tolerates_garbage():
    assert svc_get.cache_entry_from_json("not a dict") is None
    assert svc_get.cache_entry_from_json({"struct_version": 1}) is None  # missing fields


def test_load_cache_missing_file_is_empty(tmp_path):
    assert svc_get.load_cache(tmp_path / "nope.json") == {}


def test_save_and_load_cache_round_trip(tmp_path, crm):
    path = tmp_path / "cache.json"
    _, cache = svc_get.run_get_cached(crm, svc_get.GetParams(), now=_NOW, cache={}).value
    svc_get.save_cache(path, cache)
    reloaded = svc_get.load_cache(path)
    assert reloaded == cache


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
