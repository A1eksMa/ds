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

def test_get_command_returns_zero(db_path, source_dir, data_file, tmp_path):
    main(["--db", db_path, "load", str(source_dir), str(data_file)])
    out = tmp_path / "state.json"
    rc = main(["--db", db_path, "get", str(out)])
    assert rc == 0
    assert out.exists()


def test_get_command_writes_expected_records(db_path, source_dir, data_file, tmp_path):
    main(["--db", db_path, "load", "--dt", "100", str(source_dir), str(data_file)])
    out = tmp_path / "state.json"
    main(["--db", db_path, "get", str(out)])

    written = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(written["data"], key=lambda r: r["id"]) == [
        {"src": "CRM", "lb": "email", "id": "1", "val": "a@b.com"},
        {"src": "CRM", "lb": "email", "id": "2", "val": "b@b.com"},
    ]


def test_get_command_prints_count(db_path, source_dir, data_file, tmp_path, capsys):
    main(["--db", db_path, "load", str(source_dir), str(data_file)])
    out = tmp_path / "state.json"
    main(["--db", db_path, "get", str(out)])
    printed = capsys.readouterr().out
    assert "2" in printed


def test_get_command_filters_by_src(db_path, source_dir, data_file, tmp_path):
    main(["--db", db_path, "load", str(source_dir), str(data_file)])
    out = tmp_path / "state.json"
    rc = main(["--db", db_path, "get", "--src", "CRM", str(out)])
    assert rc == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["metadata"]["src"] == "CRM"


def test_get_command_unknown_src_returns_one(db_path, source_dir, data_file, tmp_path):
    main(["--db", db_path, "load", str(source_dir), str(data_file)])
    out = tmp_path / "state.json"
    rc = main(["--db", db_path, "get", "--src", "does-not-exist", str(out)])
    assert rc == 1
    assert not out.exists()


def test_get_command_until_dt_reconstructs_past_snapshot(db_path, source_dir, tmp_path):
    data1 = {"customer_id": ["1"], "email": ["v1@b.com"]}
    f1 = tmp_path / "d1.json"
    f1.write_text(json.dumps(data1), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "100", str(source_dir), str(f1)])

    data2 = {"customer_id": ["1"], "email": ["v2@b.com"]}
    f2 = tmp_path / "d2.json"
    f2.write_text(json.dumps(data2), encoding="utf-8")
    main(["--db", db_path, "load", "--dt", "200", str(source_dir), str(f2)])

    out = tmp_path / "state.json"
    main(["--db", db_path, "get", "--dt", "150", str(out)])
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["data"] == [
        {"src": "CRM", "lb": "email", "id": "1", "val": "v1@b.com"}
    ]
