import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.config.models import LabelConfig, SourceConfig
from src.domain.result import Err, Ok
from src.service import compact as svc_compact
from src.service import load as svc_load

_T1 = 1_700_000_000.0
_T2 = 1_700_100_000.0
_T3 = 1_700_200_000.0


def _cfg(name="CRM", key_label="customer_id"):
    return SourceConfig(
        name=name, key_label=key_label, p=0.5,
        labels={key_label: LabelConfig(name=key_label)},
    )


@pytest.fixture
def db():
    return InMemoryAdapter()


def _src_id(storage, name="CRM"):
    return next(s.src_id for s in storage.src_list().value if s.name == name)


# --- the textbook case from the user's own description: X, X, Z -----------

def test_repeated_value_is_flagged_first_is_not(db):
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T2)  # duplicate
    svc_load.load(db, {"customer_id": ["1"], "status": ["Z"]}, _cfg(), _T3)  # real change

    r = svc_compact.find_duplicates(db, _src_id(db))
    assert isinstance(r, Ok)
    assert len(r.value) == 1
    dup = r.value[0]
    assert dup.dt == _T2
    assert dup.active is True


def test_no_duplicates_when_every_value_differs(db):
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["1"], "status": ["Y"]}, _cfg(), _T2)
    svc_load.load(db, {"customer_id": ["1"], "status": ["Z"]}, _cfg(), _T3)

    r = svc_compact.find_duplicates(db, _src_id(db))
    assert isinstance(r, Ok)
    assert r.value == []


def test_run_of_three_identical_values_flags_all_but_first(db):
    for t in (_T1, _T2, _T3):
        svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), t)

    r = svc_compact.find_duplicates(db, _src_id(db))
    assert isinstance(r, Ok)
    assert len(r.value) == 2
    assert {d.dt for d in r.value} == {_T2, _T3}


def test_delete_marker_repeat_is_also_a_duplicate(db):
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["1"], "status": [None]}, _cfg(), _T2)  # DELETE
    svc_load.load(db, {"customer_id": ["1"], "status": [None]}, _cfg(), _T3)  # still deleted -> dup

    r = svc_compact.find_duplicates(db, _src_id(db))
    assert isinstance(r, Ok)
    assert len(r.value) == 1
    assert r.value[0].dt == _T3
    assert r.value[0].val == 0


def test_different_keys_are_independent(db):
    svc_load.load(db, {"customer_id": ["1", "2"], "status": ["X", "A"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["1", "2"], "status": ["X", "B"]}, _cfg(), _T2)

    r = svc_compact.find_duplicates(db, _src_id(db))
    assert isinstance(r, Ok)
    assert len(r.value) == 1  # only customer 1's repeat -- customer 2 changed (A -> B)


# --- active vs archived ----------------------------------------------------

def test_duplicate_already_in_archive_is_flagged_but_not_active(db):
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T2)
    src_id = _src_id(db)
    db.txn_archive(src_id=src_id, until_dt=_T2)  # archive both

    r = svc_compact.find_duplicates(db, src_id)
    assert isinstance(r, Ok)
    assert len(r.value) == 1
    assert r.value[0].active is False


def test_finds_duplicates_that_span_active_and_archive(db):
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T1)
    src_id = _src_id(db)
    db.txn_archive(src_id=src_id, until_dt=_T1)  # first entry archived
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T2)  # active, dup of archived

    r = svc_compact.find_duplicates(db, src_id)
    assert isinstance(r, Ok)
    assert len(r.value) == 1
    assert r.value[0].dt == _T2
    assert r.value[0].active is True


# --- date-windowed scan: the user's "skip the first, don't need context" rule --

def test_date_window_treats_first_in_window_as_anchor_even_if_it_duplicates_earlier(db):
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T2)  # would be a dup of T1
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T3)  # dup of T2 too

    # window starts at T2: T2 becomes the anchor (never flagged), T3 (same value) is the only dup
    r = svc_compact.find_duplicates(db, _src_id(db), from_dt=_T2)
    assert isinstance(r, Ok)
    assert len(r.value) == 1
    assert r.value[0].dt == _T3


def test_date_window_upper_bound_excludes_later_transactions(db):
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T1)
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T2)
    svc_load.load(db, {"customer_id": ["1"], "status": ["X"]}, _cfg(), _T3)

    r = svc_compact.find_duplicates(db, _src_id(db), until_dt=_T2)
    assert isinstance(r, Ok)
    assert len(r.value) == 1
    assert r.value[0].dt == _T2  # T3 is outside the window, not considered at all


# --- scoping by lb/id -------------------------------------------------------

def test_scoped_to_one_label(db):
    svc_load.load(db, {
        "customer_id": ["1"], "status": ["X"], "email": ["a@e.com"],
    }, _cfg(), _T1)
    svc_load.load(db, {
        "customer_id": ["1"], "status": ["X"], "email": ["a@e.com"],
    }, _cfg(), _T2)  # both status and email repeat

    src_id = _src_id(db)
    lb_id = next(l.lb_id for l in db.lb_list(src_id).value if l.name == "status")

    r = svc_compact.find_duplicates(db, src_id, lb_ids=[lb_id])
    assert isinstance(r, Ok)
    assert len(r.value) == 1
    assert r.value[0].lb_id == lb_id
