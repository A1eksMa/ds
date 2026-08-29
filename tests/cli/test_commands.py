import json

import pytest

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
