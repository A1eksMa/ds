import json

from src.config.loader import load_source
from src.config.models import LabelConfig, SourceConfig
from src.config.writer import write_source
from src.domain.result import Ok


def test_write_source_roundtrips_through_load_source(tmp_path):
    d = tmp_path / "CRM"
    d.mkdir()
    cfg = SourceConfig(
        name="CRM", key_label="customer_id", p=0.9, description="CRM system",
        labels={
            "email": LabelConfig(name="email", type="text"),
            "revenue": LabelConfig(name="revenue", type="number", publish=False),
            "internal_note": LabelConfig(name="internal_note", archive=True, p=0.8, description="note"),
        },
    )
    result = write_source(d / "source.json", cfg)
    assert isinstance(result, Ok)

    loaded = load_source(d)
    assert isinstance(loaded, Ok)
    got = loaded.value
    assert got.name == "CRM"
    assert got.key_label == "customer_id"
    assert got.p == 0.9
    assert got.description == "CRM system"
    assert got.labels["email"].type == "text"
    assert got.labels["revenue"].type == "number"
    assert got.labels["revenue"].publish is False
    assert got.labels["internal_note"].archive is True
    assert got.labels["internal_note"].p == 0.8
    assert got.labels["internal_note"].description == "note"


def test_write_source_omits_defaults_for_readability(tmp_path):
    d = tmp_path / "CRM"
    d.mkdir()
    cfg = SourceConfig(
        name="CRM", key_label="customer_id",
        labels={"email": LabelConfig(name="email")},  # everything at default
    )
    write_source(d / "source.json", cfg)

    doc = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert doc == {
        "name": "CRM", "key_label": "customer_id",
        "labels": [{"name": "email"}],
    }


def test_write_source_no_labels_key_when_empty(tmp_path):
    d = tmp_path / "S"
    d.mkdir()
    write_source(d / "source.json", SourceConfig(name="S", key_label="id"))

    doc = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert "labels" not in doc


def test_write_source_key_label_sorted_first(tmp_path):
    d = tmp_path / "CRM"
    d.mkdir()
    cfg = SourceConfig(
        name="CRM", key_label="customer_id",
        labels={
            "email": LabelConfig(name="email"),
            "customer_id": LabelConfig(name="customer_id"),
            "aaa": LabelConfig(name="aaa"),
        },
    )
    write_source(d / "source.json", cfg)

    doc = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert [l["name"] for l in doc["labels"]] == ["customer_id", "aaa", "email"]
