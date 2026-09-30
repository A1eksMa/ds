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
