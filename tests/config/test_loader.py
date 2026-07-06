import json

import pytest

from src.config.loader import load_source
from src.domain.result import Err, Ok


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def crm_dir(tmp_path):
    d = tmp_path / "CRM"
    d.mkdir()
    _write(d / "source.json", {
        "name": "CRM",
        "key_label": "customer_id",
        "p": 0.9,
        "description": "CRM system",
    })
    return d


def test_load_source_basic_fields(crm_dir):
    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    cfg = result.value
    assert cfg.name == "CRM"
    assert cfg.key_label == "customer_id"
    assert cfg.p == 0.9
    assert cfg.description == "CRM system"


def test_load_source_no_labels_dir(crm_dir):
    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    assert result.value.labels == {}


def test_load_source_with_labels(crm_dir):
    labels_dir = crm_dir / "labels"
    for name, p in [("customer_id", 1.0), ("email", 0.8), ("phone", 0.7)]:
        d = labels_dir / name
        d.mkdir(parents=True)
        _write(d / "config.json", {"name": name, "p": p})

    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    cfg = result.value
    assert set(cfg.labels.keys()) == {"customer_id", "email", "phone"}
    assert cfg.labels["email"].p == 0.8


def test_load_source_label_defaults(crm_dir):
    d = crm_dir / "labels" / "email"
    d.mkdir(parents=True)
    _write(d / "config.json", {"name": "email"})

    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    assert result.value.labels["email"].p == 0.5
    assert result.value.labels["email"].description is None


def test_load_source_defaults(tmp_path):
    d = tmp_path / "S"
    d.mkdir()
    _write(d / "source.json", {"name": "S", "key_label": "id"})

    result = load_source(d)
    assert isinstance(result, Ok)
    assert result.value.p == 0.5
    assert result.value.description is None


def test_load_source_missing_directory(tmp_path):
    result = load_source(tmp_path / "nonexistent")
    assert isinstance(result, Err)


def test_load_source_missing_required_field(tmp_path):
    d = tmp_path / "bad"
    d.mkdir()
    _write(d / "source.json", {"name": "bad"})  # key_label отсутствует
    result = load_source(d)
    assert isinstance(result, Err)


def test_load_source_ignores_files_in_labels_dir(crm_dir):
    labels_dir = crm_dir / "labels"
    labels_dir.mkdir()
    (labels_dir / "README.txt").write_text("ignore me")

    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    assert result.value.labels == {}


def test_load_source_ignores_label_dir_without_config(crm_dir):
    d = crm_dir / "labels" / "orphan"
    d.mkdir(parents=True)
    # нет config.json

    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    assert result.value.labels == {}
