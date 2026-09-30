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


def test_load_source_no_labels_key(crm_dir):
    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    assert result.value.labels == {}


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


# --- inline `labels` list (source.json), replaces the old labels/<name>/config.json dirs ---

def test_load_source_with_inline_labels(crm_dir):
    data = json.loads((crm_dir / "source.json").read_text())
    data["labels"] = [
        {"name": "email", "type": "text", "p": 0.8},
        {"name": "revenue", "type": "number"},
        {"name": "internal_flag", "type": "bool", "archive": True, "publish": False},
    ]
    _write(crm_dir / "source.json", data)

    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    labels = result.value.labels
    assert set(labels.keys()) == {"email", "revenue", "internal_flag"}
    assert labels["email"].type == "text"
    assert labels["email"].p == 0.8
    assert labels["revenue"].type == "number"
    assert labels["internal_flag"].archive is True
    assert labels["internal_flag"].publish is False


def test_load_source_explicit_publish_true_overrides_default(crm_dir):
    data = json.loads((crm_dir / "source.json").read_text())
    data["labels"] = [{"name": "email", "publish": True}]
    _write(crm_dir / "source.json", data)

    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    assert result.value.labels["email"].publish is True


def test_load_source_label_defaults(crm_dir):
    data = json.loads((crm_dir / "source.json").read_text())
    data["labels"] = [{"name": "email"}]
    _write(crm_dir / "source.json", data)

    result = load_source(crm_dir)
    assert isinstance(result, Ok)
    email = result.value.labels["email"]
    assert email.type == "text"
    assert email.archive is False
    assert email.publish is False
    assert email.p == 0.5
    assert email.description is None


@pytest.mark.parametrize("bad_type", ["money", "TEXT", "", "int"])
def test_load_source_rejects_invalid_label_type(crm_dir, bad_type):
    data = json.loads((crm_dir / "source.json").read_text())
    data["labels"] = [{"name": "x", "type": bad_type}]
    _write(crm_dir / "source.json", data)

    result = load_source(crm_dir)
    assert isinstance(result, Err)


def test_load_source_rejects_non_list_labels(crm_dir):
    data = json.loads((crm_dir / "source.json").read_text())
    data["labels"] = {"email": {"type": "text"}}
    _write(crm_dir / "source.json", data)

    result = load_source(crm_dir)
    assert isinstance(result, Err)


def test_load_source_rejects_non_object_label_entry(crm_dir):
    data = json.loads((crm_dir / "source.json").read_text())
    data["labels"] = ["email"]
    _write(crm_dir / "source.json", data)

    result = load_source(crm_dir)
    assert isinstance(result, Err)


def test_load_source_rejects_label_entry_missing_name(crm_dir):
    data = json.loads((crm_dir / "source.json").read_text())
    data["labels"] = [{"type": "text"}]
    _write(crm_dir / "source.json", data)

    result = load_source(crm_dir)
    assert isinstance(result, Err)
