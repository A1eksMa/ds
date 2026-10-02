import json

import pytest

from src.adapters.sqlite_adapter import SQLiteAdapter
from src.cli.commands import main


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def source_dir(tmp_path):
    d = tmp_path / "CRM"
    d.mkdir()
    (d / "source.json").write_text(
        json.dumps({"name": "CRM", "key_label": "customer_id"}),
        encoding="utf-8",
    )
    return d


@pytest.fixture
def data_file(tmp_path):
    data = {"customer_id": ["1", "2"], "email": ["a@b.com", "b@b.com"]}
    f = tmp_path / "data.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


# --- load command ---

def test_load_command_returns_zero(db_path, source_dir, data_file):
    rc = main(["--db", db_path, "load", str(source_dir), str(data_file)])
    assert rc == 0


def test_load_command_missing_data_file(db_path, source_dir, tmp_path):
    rc = main(["--db", db_path, "load", str(source_dir), str(tmp_path / "missing.json")])
    assert rc == 1


def test_load_command_bad_source_dir(db_path, tmp_path, data_file):
    rc = main(["--db", db_path, "load", str(tmp_path / "no_such_dir"), str(data_file)])
    assert rc == 1


def test_load_command_prints_count(db_path, source_dir, data_file, capsys):
    main(["--db", db_path, "load", str(source_dir), str(data_file)])
    out = capsys.readouterr().out
    assert "2" in out


def test_load_accumulates_transactions(db_path, source_dir, tmp_path):
    data1 = {"customer_id": ["1"], "email": ["a@b.com"]}
    f1 = tmp_path / "d1.json"
    f1.write_text(json.dumps(data1), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "100", str(source_dir), str(f1)])

    data2 = {"customer_id": ["2"], "email": ["b@b.com"]}
    f2 = tmp_path / "d2.json"
    f2.write_text(json.dumps(data2), encoding="utf-8")
    rc = main(["--db", db_path, "load", "--dt", "200", str(source_dir), str(f2)])
    assert rc == 0


def test_load_command_archive_flagged_label_end_to_end(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id",
        "labels": [
            {"name": "email", "type": "text"},
            {"name": "internal_note", "type": "text", "archive": True},
        ],
    }), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({
        "customer_id": ["1"], "email": ["a@b.com"], "internal_note": ["only for auditors"],
    }), encoding="utf-8")

    rc = main(["--db", db_path, "load", str(d), str(data), "--dt", "1700000000"])
    assert rc == 0
    capsys.readouterr()

    main(["--db", db_path, "get", "--dt", "1700000000"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"][0].get("email") == "a@b.com"
    assert "internal_note" not in doc["data"][0]  # archived, not active -> not in the default fold

    main(["--db", db_path, "get", "--dt", "1700000000", "--archive"])
    doc_full = json.loads(capsys.readouterr().out)
    assert doc_full["data"][0]["internal_note"] == "only for auditors"


# --- upload command ---

def test_upload_command_succeeds_when_schema_and_types_match(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id",
        "labels": [{"name": "revenue", "type": "number"}],
    }), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"customer_id": ["1"], "revenue": ["100"]}), encoding="utf-8")

    rc = main(["--db", db_path, "upload", str(d), str(data), "--dt", "1700000000"])
    assert rc == 0
    assert "uploaded 1 transaction(s)" in capsys.readouterr().out


def test_upload_command_rejects_unknown_label_and_loads_nothing(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id", "labels": [{"name": "email"}],
    }), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({
        "customer_id": ["1"], "email": ["a@b.com"], "phone": ["+1"],
    }), encoding="utf-8")

    rc = main(["--db", db_path, "upload", str(d), str(data), "--dt", "1700000000"])
    assert rc == 1
    assert "unknown label 'phone'" in capsys.readouterr().err

    storage = SQLiteAdapter(db_path)
    assert storage.src_list().value == []  # nothing loaded at all -- not even "email"


def test_upload_command_rejects_bad_type_and_loads_nothing(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id",
        "labels": [{"name": "email"}, {"name": "revenue", "type": "number"}],
    }), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({
        "customer_id": ["1"], "email": ["a@b.com"], "revenue": ["not-a-number"],
    }), encoding="utf-8")

    rc = main(["--db", db_path, "upload", str(d), str(data), "--dt", "1700000000"])
    assert rc == 1
    assert "does not parse" in capsys.readouterr().err

    storage = SQLiteAdapter(db_path)
    assert storage.src_list().value == []


def test_upload_command_allows_null_in_a_typed_column(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id",
        "labels": [{"name": "revenue", "type": "number"}],
    }), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"customer_id": ["1"], "revenue": [None]}), encoding="utf-8")

    rc = main(["--db", db_path, "upload", str(d), str(data), "--dt", "1700000000"])
    assert rc == 0


def test_upload_command_works_on_brand_new_source_with_declared_labels(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id", "labels": [{"name": "email"}],
    }), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"customer_id": ["1"], "email": ["a@b.com"]}), encoding="utf-8")

    rc = main(["--db", db_path, "upload", str(d), str(data), "--dt", "1700000000"])
    assert rc == 0
    assert "uploaded 1 transaction(s)" in capsys.readouterr().out


def test_upload_command_second_batch_accepts_labels_learned_from_first_load(db_path, source_dir, tmp_path, capsys):
    # plain `ds load` first (source.json declares nothing) -- "email" becomes known from the DB
    data1 = tmp_path / "d1.json"
    data1.write_text(json.dumps({"customer_id": ["1"], "email": ["a@b.com"]}), encoding="utf-8")
    main(["--db", db_path, "load", str(source_dir), str(data1), "--dt", "1700000000"])
    capsys.readouterr()

    data2 = tmp_path / "d2.json"
    data2.write_text(json.dumps({"customer_id": ["2"], "email": ["b@b.com"]}), encoding="utf-8")
    rc = main(["--db", db_path, "upload", str(source_dir), str(data2), "--dt", "1700100000"])
    assert rc == 0
    assert "uploaded 1 transaction(s)" in capsys.readouterr().out


# --- update command ---

def test_update_command_adds_and_removes_labels(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    source_json = d / "source.json"
    source_json.write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id",
        "labels": [{"name": "junk_field", "type": "text"}],
    }), encoding="utf-8")
    # junk_field never actually shows up in any loaded data; "phone" shows up
    # ad hoc without ever being declared
    data = tmp_path / "data.json"
    data.write_text(json.dumps({
        "customer_id": ["1"], "email": ["a@b.com"], "phone": ["+1"],
    }), encoding="utf-8")
    main(["--db", db_path, "load", str(d), str(data), "--dt", "1700000000"])
    capsys.readouterr()

    rc = main(["--db", db_path, "update", str(d)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "added: email, phone" in out
    assert "removed: junk_field" in out

    doc = json.loads(source_json.read_text(encoding="utf-8"))
    names = {l["name"] for l in doc["labels"]}
    assert names == {"email", "phone"}


def test_update_command_preserves_existing_label_config(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    source_json = d / "source.json"
    source_json.write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id",
        "labels": [{"name": "revenue", "type": "number", "archive": True, "p": 0.9}],
    }), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"customer_id": ["1"], "revenue": ["100"]}), encoding="utf-8")
    main(["--db", db_path, "load", str(d), str(data), "--dt", "1700000000"])
    capsys.readouterr()

    rc = main(["--db", db_path, "update", str(d)])
    assert rc == 0
    assert "already up to date" in capsys.readouterr().out

    doc = json.loads(source_json.read_text(encoding="utf-8"))
    revenue = next(l for l in doc["labels"] if l["name"] == "revenue")
    assert revenue == {"name": "revenue", "type": "number", "archive": True, "p": 0.9}


def test_update_command_key_label_survives_even_without_data(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    source_json = d / "source.json"
    source_json.write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id",
        "labels": [{"name": "customer_id"}, {"name": "email"}],
    }), encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"customer_id": ["1"], "email": ["a@b.com"]}), encoding="utf-8")
    main(["--db", db_path, "load", str(d), str(data), "--dt", "1700000000"])
    capsys.readouterr()

    rc = main(["--db", db_path, "update", str(d)])
    assert rc == 0
    assert "already up to date" in capsys.readouterr().out

    doc = json.loads(source_json.read_text(encoding="utf-8"))
    assert {l["name"] for l in doc["labels"]} == {"customer_id", "email"}


def test_update_command_unknown_source_is_an_error(db_path, tmp_path, capsys):
    d = tmp_path / "CRM"
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "name": "CRM", "key_label": "customer_id",
        "labels": [{"name": "email"}],
    }), encoding="utf-8")
    # never loaded -- CRM doesn't exist in this fresh --db yet
    rc = main(["--db", db_path, "update", str(d)])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


# --- get command ---

def _seed(db_path, source_dir, tmp_path, capsys):
    d1 = tmp_path / "b1.json"
    d1.write_text(json.dumps({
        "customer_id": ["101", "102"], "email": ["a@e.com", "b@e.com"], "phone": ["+1", None],
    }), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "1700000000", str(source_dir), str(d1)])
    d2 = tmp_path / "b2.json"
    d2.write_text(json.dumps({
        "customer_id": ["102"], "email": ["b.new@e.com"],
    }), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "1700100000", str(source_dir), str(d2)])
    capsys.readouterr()  # drop the load output so tests can read the get output cleanly


def test_get_command_stdout_single_source(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "get", "--dt", "1700100000"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["meta"]["name"] == "CRM"
    row102 = next(r for r in doc["data"] if r["customer_id"] == "102")
    assert row102["email"] == "b.new@e.com"


def test_get_command_writes_files(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    out_dir = tmp_path / "out"
    rc = main(["--db", db_path, "get", "--out", str(out_dir), "--dt", "1700100000"])
    assert rc == 0
    assert "wrote 1 file(s)" in capsys.readouterr().out
    doc = json.loads((out_dir / "CRM.json").read_text(encoding="utf-8"))
    assert doc["meta"]["rows"] == 2


def test_get_command_unknown_source(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "get", "--src", "ERP"])
    assert rc == 1


def test_get_command_with_preset(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    preset = tmp_path / "preset.json"
    preset.write_text(json.dumps({
        "query": {"as_of": 1700000000, "sources": {"CRM": {"labels": ["email"]}}},
    }), encoding="utf-8")
    rc = main(["--db", db_path, "get", "--preset", str(preset)])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["meta"]["labels"] == ["email"]
    assert doc["meta"]["as_of"] == 1700000000.0
    assert {r["customer_id"] for r in doc["data"]} == {"101", "102"}


def test_get_command_flag_overrides_preset_dt(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    preset = tmp_path / "preset.json"
    preset.write_text(json.dumps({"query": {"as_of": 1700000000}}), encoding="utf-8")
    main(["--db", db_path, "get", "--preset", str(preset), "--dt", "1700100000"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["meta"]["as_of"] == 1700100000.0
    row102 = next(r for r in doc["data"] if r["customer_id"] == "102")
    assert row102["email"] == "b.new@e.com"


# --- delete command ---

def test_delete_command_unknown_source(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "delete", "--src", "ERP", "--yes"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_delete_command_unknown_label(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--lb", "fax", "--yes"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_delete_command_with_yes_removes_active_transactions(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--lb", "phone", "--yes"])
    assert rc == 0
    assert "deleted 2 transaction(s)" in capsys.readouterr().out

    rc = main(["--db", db_path, "get", "--src", "CRM", "--lb", "phone"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"] == []


def test_delete_command_also_removes_archived_transactions(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    storage = SQLiteAdapter(db_path)
    archived = storage.txn_archive(until_dt=1_800_000_000)
    assert archived.value > 0

    rc = main(["--db", db_path, "delete", "--src", "CRM", "--yes"])
    assert rc == 0
    capsys.readouterr()

    src_id = next(s.src_id for s in storage.src_list().value if s.name == "CRM")
    assert storage.txn_query(src_id=src_id, include_archive=True).value == []


def test_delete_command_zero_matches_reports_zero_without_prompting(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    main(["--db", db_path, "delete", "--src", "CRM", "--lb", "phone", "--yes"])
    capsys.readouterr()

    # second delete of the now-empty label: nothing to confirm, no prompt needed
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--lb", "phone"])
    assert rc == 0
    assert "deleted 0 transaction(s)" in capsys.readouterr().out


def test_delete_command_without_yes_aborts_when_stdin_unavailable(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--lb", "phone"])
    assert rc == 1
    assert "aborted" in capsys.readouterr().err


def test_delete_command_without_yes_respects_declined_prompt(db_path, source_dir, tmp_path, capsys, monkeypatch):
    _seed(db_path, source_dir, tmp_path, capsys)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--lb", "phone"])
    assert rc == 1
    assert "aborted" in capsys.readouterr().err

    rc = main(["--db", db_path, "get", "--src", "CRM", "--lb", "phone"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"] != []  # declined -- phone transactions still there


def test_delete_command_without_yes_respects_accepted_prompt(db_path, source_dir, tmp_path, capsys, monkeypatch):
    _seed(db_path, source_dir, tmp_path, capsys)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--lb", "phone"])
    assert rc == 0
    assert "deleted 2 transaction(s)" in capsys.readouterr().out


def test_delete_command_by_id(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--id", "101", "--yes"])
    assert rc == 0
    assert "deleted 2 transaction(s)" in capsys.readouterr().out  # 101: email + phone

    rc = main(["--db", db_path, "get", "--src", "CRM"])
    doc = json.loads(capsys.readouterr().out)
    assert {r["customer_id"] for r in doc["data"]} == {"102"}


def test_delete_command_unknown_id(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--id", "no-such-id", "--yes"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_delete_command_by_where(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    # 102's email was updated to "b.new@e.com" in the second batch
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--where", "email=b.new@e.com", "--yes"])
    assert rc == 0
    capsys.readouterr()

    rc = main(["--db", db_path, "get", "--src", "CRM"])
    doc = json.loads(capsys.readouterr().out)
    assert {r["customer_id"] for r in doc["data"]} == {"101"}


def test_delete_command_id_and_where_are_mutually_exclusive(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--id", "101", "--where", "email=x", "--yes"])
    assert rc == 1
    assert "mutually exclusive" in capsys.readouterr().err


def test_delete_command_by_cnt(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    storage = SQLiteAdapter(db_path)
    src_id = next(s.src_id for s in storage.src_list().value if s.name == "CRM")
    one_cnt = int(storage.txn_query(src_id=src_id).value[0].cnt)

    rc = main(["--db", db_path, "delete", "--src", "CRM", "--cnt", str(one_cnt), "--yes"])
    assert rc == 0
    assert "deleted 1 transaction(s)" in capsys.readouterr().out
    assert storage.txn_query(src_id=src_id, cnts=[one_cnt], include_archive=True).value == []


def test_delete_command_cnt_not_combinable_with_lb(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--cnt", "1", "--lb", "email", "--yes"])
    assert rc == 1
    assert "cannot be combined" in capsys.readouterr().err


def test_delete_command_dt_range(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    # only the first batch (dt=1700000000) falls in this range; second batch (dt=1700100000) doesn't
    rc = main([
        "--db", db_path, "delete", "--src", "CRM",
        "--dt-from", "1699999999", "--dt-until", "1700000001", "--yes",
    ])
    assert rc == 0
    capsys.readouterr()

    rc = main(["--db", db_path, "get", "--src", "CRM", "--archive"])
    doc = json.loads(capsys.readouterr().out)
    # 102's email update from batch 2 (dt=1700100000) must have survived
    row102 = next(r for r in doc["data"] if r["customer_id"] == "102")
    assert row102["email"] == "b.new@e.com"


def test_delete_command_created_range_excludes_everything_loaded_earlier(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    # a created_at window strictly before "now" (when _seed's loads actually ran) matches nothing
    rc = main(["--db", db_path, "delete", "--src", "CRM", "--created-until", "0", "--yes"])
    assert rc == 0
    assert "deleted 0 transaction(s)" in capsys.readouterr().out


# --- archive command ---

def test_archive_command_moves_without_deleting(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "archive", "--src", "CRM", "--lb", "phone", "--yes"])
    assert rc == 0
    assert "archived 2 transaction(s)" in capsys.readouterr().out

    rc = main(["--db", db_path, "get", "--src", "CRM", "--lb", "phone"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"] == []  # gone from the active fold ...

    rc = main(["--db", db_path, "get", "--src", "CRM", "--lb", "phone", "--archive"])
    doc_full = json.loads(capsys.readouterr().out)
    assert doc_full["data"] != []  # ... but still there, unlike delete


def test_archive_command_unknown_source(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "archive", "--src", "ERP", "--yes"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_archive_command_by_where(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "archive", "--src", "CRM", "--where", "email=b.new@e.com", "--yes"])
    assert rc == 0
    capsys.readouterr()

    rc = main(["--db", db_path, "get", "--src", "CRM"])
    doc = json.loads(capsys.readouterr().out)
    assert {r["customer_id"] for r in doc["data"]} == {"101"}  # 102 archived out of the active fold


def test_archive_command_without_yes_respects_declined_prompt(db_path, source_dir, tmp_path, capsys, monkeypatch):
    _seed(db_path, source_dir, tmp_path, capsys)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    rc = main(["--db", db_path, "archive", "--src", "CRM", "--lb", "phone"])
    assert rc == 1
    assert "aborted" in capsys.readouterr().err


# --- unarchive command ---

def test_unarchive_command_moves_back(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    main(["--db", db_path, "archive", "--src", "CRM", "--lb", "phone", "--yes"])
    capsys.readouterr()

    rc = main(["--db", db_path, "unarchive", "--src", "CRM", "--lb", "phone", "--yes"])
    assert rc == 0
    assert "unarchived 2 transaction(s)" in capsys.readouterr().out

    rc = main(["--db", db_path, "get", "--src", "CRM", "--lb", "phone"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"] != []  # back in the active fold


def test_unarchive_command_unknown_source(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    rc = main(["--db", db_path, "unarchive", "--src", "ERP", "--yes"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_unarchive_command_by_where(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    main(["--db", db_path, "archive", "--src", "CRM", "--where", "email=b.new@e.com", "--yes"])
    capsys.readouterr()

    rc = main(["--db", db_path, "unarchive", "--src", "CRM", "--where", "email=b.new@e.com", "--yes"])
    assert rc == 0
    capsys.readouterr()

    rc = main(["--db", db_path, "get", "--src", "CRM"])
    doc = json.loads(capsys.readouterr().out)
    assert {r["customer_id"] for r in doc["data"]} == {"101", "102"}  # 102 back in the active fold


def test_unarchive_command_zero_matches_reports_zero_without_prompting(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)
    capsys.readouterr()

    rc = main(["--db", db_path, "unarchive", "--src", "CRM", "--created-until", "0"])
    assert rc == 0
    assert "unarchived 0 transaction(s)" in capsys.readouterr().out


def test_unarchive_command_without_yes_respects_declined_prompt(db_path, source_dir, tmp_path, capsys, monkeypatch):
    _seed(db_path, source_dir, tmp_path, capsys)
    main(["--db", db_path, "archive", "--src", "CRM", "--lb", "phone", "--yes"])
    capsys.readouterr()

    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    rc = main(["--db", db_path, "unarchive", "--src", "CRM", "--lb", "phone"])
    assert rc == 1
    assert "aborted" in capsys.readouterr().err


# --- mv command ---

def test_mv_command_renames_within_same_source(db_path, source_dir, tmp_path, capsys):
    d1 = tmp_path / "b1.json"
    d1.write_text(json.dumps({
        "customer_id": ["101", "102"], "old_name": ["a", "b"],
    }), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "1700000000", str(source_dir), str(d1)])
    capsys.readouterr()

    rc = main(["--db", db_path, "mv", "--src", "CRM", "--lb", "old_name", "--to-lb", "new_name", "--yes"])
    assert rc == 0
    assert "moved 2 transaction(s)" in capsys.readouterr().out

    rc = main(["--db", db_path, "get", "--src", "CRM"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["meta"]["labels"] == ["new_name"]
    assert {r["new_name"] for r in doc["data"]} == {"a", "b"}


def test_mv_command_merges_transition_period(db_path, source_dir, tmp_path, capsys):
    d1 = tmp_path / "b1.json"
    d1.write_text(json.dumps({"customer_id": ["101"], "old_name": ["a"]}), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "1700000000", str(source_dir), str(d1)])
    d2 = tmp_path / "b2.json"
    d2.write_text(json.dumps({"customer_id": ["102"], "new_name": ["b"]}), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "1700100000", str(source_dir), str(d2)])
    capsys.readouterr()

    rc = main(["--db", db_path, "mv", "--src", "CRM", "--lb", "old_name", "--to-lb", "new_name", "--yes"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "moved 1 transaction(s)" in out
    assert "merged into existing label" in out

    rc = main(["--db", db_path, "get", "--src", "CRM"])
    doc = json.loads(capsys.readouterr().out)
    values = {r["customer_id"]: r["new_name"] for r in doc["data"]}
    assert values == {"101": "a", "102": "b"}


def test_mv_command_to_new_source_creates_it(db_path, source_dir, tmp_path, capsys):
    d1 = tmp_path / "b1.json"
    d1.write_text(json.dumps({"customer_id": ["101"], "old_name": ["a"]}), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "1700000000", str(source_dir), str(d1)])
    capsys.readouterr()

    rc = main([
        "--db", db_path, "mv", "--src", "CRM", "--lb", "old_name",
        "--to-src", "ERP", "--to-lb", "new_name", "--yes",
    ])
    assert rc == 0
    assert "moved 1 transaction(s)" in capsys.readouterr().out

    rc = main(["--db", db_path, "get", "--src", "ERP"])
    doc = json.loads(capsys.readouterr().out)
    # ERP didn't exist before `mv` created it -- its key_label is only bootstrapped by
    # `ds load`'s first batch (see service/load.py), so `ds get` falls back to "id"
    assert doc["data"] == [{"id": "101", "new_name": "a"}]


def test_mv_command_unknown_source(db_path, source_dir, tmp_path, capsys):
    main(["--db", db_path, "mv", "--src", "ERP", "--lb", "x", "--to-lb", "y", "--yes"])
    assert "not found" in capsys.readouterr().err


def test_mv_command_refuses_key_label(db_path, source_dir, tmp_path, capsys):
    d1 = tmp_path / "b1.json"
    d1.write_text(json.dumps({"customer_id": ["101"]}), encoding="utf-8")
    main(["--db", db_path, "load", str(source_dir), str(d1)])
    capsys.readouterr()

    rc = main(["--db", db_path, "mv", "--src", "CRM", "--lb", "customer_id", "--to-lb", "new_name", "--yes"])
    assert rc == 1
    assert "key label" in capsys.readouterr().err


def test_mv_command_without_yes_respects_declined_prompt(db_path, source_dir, tmp_path, capsys, monkeypatch):
    d1 = tmp_path / "b1.json"
    d1.write_text(json.dumps({"customer_id": ["101"], "old_name": ["a"]}), encoding="utf-8")
    main(["--db", db_path, "load", str(source_dir), str(d1)])
    capsys.readouterr()

    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    rc = main(["--db", db_path, "mv", "--src", "CRM", "--lb", "old_name", "--to-lb", "new_name"])
    assert rc == 1
    assert "aborted" in capsys.readouterr().err

    # declining must leave the database untouched
    rc = main(["--db", db_path, "get", "--src", "CRM"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["meta"]["labels"] == ["old_name"]


# --- compact command ---

def _seed_with_duplicate(db_path, source_dir, tmp_path):
    b1 = tmp_path / "c1.json"
    b1.write_text(json.dumps({"customer_id": ["1"], "status": ["active"]}), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "1700000000", str(source_dir), str(b1)])
    b2 = tmp_path / "c2.json"
    b2.write_text(json.dumps({"customer_id": ["1"], "status": ["active"]}), encoding="utf-8")  # duplicate
    main(["--db", db_path, "load", "--dt", "1700100000", str(source_dir), str(b2)])
    b3 = tmp_path / "c3.json"
    b3.write_text(json.dumps({"customer_id": ["1"], "status": ["inactive"]}), encoding="utf-8")  # real change
    main(["--db", db_path, "load", "--dt", "1700200000", str(source_dir), str(b3)])


def test_compact_command_soft_archives_duplicate(db_path, source_dir, tmp_path, capsys):
    _seed_with_duplicate(db_path, source_dir, tmp_path)
    capsys.readouterr()

    rc = main(["--db", db_path, "compact", "--src", "CRM", "--yes"])
    assert rc == 0
    assert "archived 1 duplicate transaction(s)" in capsys.readouterr().out

    storage = SQLiteAdapter(db_path)
    src_id = next(s.src_id for s in storage.src_list().value if s.name == "CRM")
    assert len(storage.txn_query(src_id=src_id).value) == 2          # one moved out
    assert len(storage.txn_query(src_id=src_id, include_archive=True).value) == 3  # still there overall


def test_compact_command_hard_deletes_with_flag(db_path, source_dir, tmp_path, capsys):
    _seed_with_duplicate(db_path, source_dir, tmp_path)
    capsys.readouterr()

    rc = main(["--db", db_path, "compact", "--src", "CRM", "--hard", "--yes"])
    assert rc == 0
    assert "deleted 1 duplicate transaction(s)" in capsys.readouterr().out

    storage = SQLiteAdapter(db_path)
    src_id = next(s.src_id for s in storage.src_list().value if s.name == "CRM")
    assert len(storage.txn_query(src_id=src_id, include_archive=True).value) == 2  # gone for good


def test_compact_command_no_duplicates(db_path, source_dir, tmp_path, capsys):
    _seed(db_path, source_dir, tmp_path, capsys)  # _seed's batches never repeat a value
    rc = main(["--db", db_path, "compact", "--src", "CRM", "--yes"])
    assert rc == 0
    assert "archived 0 duplicate transaction(s)" in capsys.readouterr().out


def test_compact_command_unknown_source(db_path, source_dir, tmp_path, capsys):
    _seed_with_duplicate(db_path, source_dir, tmp_path)
    rc = main(["--db", db_path, "compact", "--src", "ERP", "--yes"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_compact_command_prompt_shows_sample_and_respects_decline(db_path, source_dir, tmp_path, capsys, monkeypatch):
    _seed_with_duplicate(db_path, source_dir, tmp_path)
    capsys.readouterr()
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    rc = main(["--db", db_path, "compact", "--src", "CRM"])
    assert rc == 1
    out = capsys.readouterr()
    assert "CRM.status.1" in out.out  # the sample line names source.label.key
    assert "aborted" in out.err

    storage = SQLiteAdapter(db_path)
    src_id = next(s.src_id for s in storage.src_list().value if s.name == "CRM")
    assert len(storage.txn_query(src_id=src_id).value) == 3  # declined -- nothing moved


def test_compact_command_dt_from_anchors_the_window(db_path, source_dir, tmp_path, capsys):
    # window starting at the second batch: that duplicate becomes the anchor and is spared;
    # without --dt-from the same run would have archived it (see test above)
    _seed_with_duplicate(db_path, source_dir, tmp_path)
    capsys.readouterr()

    rc = main(["--db", db_path, "compact", "--src", "CRM", "--dt-from", "1700100000", "--yes"])
    assert rc == 0
    assert "archived 0 duplicate transaction(s)" in capsys.readouterr().out
