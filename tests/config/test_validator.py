from src.config.models import LabelConfig, SourceConfig
from src.config import validator
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok


def _src(key_label="id", p=0.5, labels=None):
    if labels is None:
        labels = {key_label: LabelConfig(name=key_label)}
    return SourceConfig(name="CRM", key_label=key_label, p=p, labels=labels)


# --- validate_label ---

def test_validate_label_valid():
    assert isinstance(validator.validate_label(LabelConfig(name="email", p=0.8)), Ok)


def test_validate_label_p_boundary_zero():
    assert isinstance(validator.validate_label(LabelConfig(name="x", p=0.0)), Ok)


def test_validate_label_p_boundary_one():
    assert isinstance(validator.validate_label(LabelConfig(name="x", p=1.0)), Ok)


def test_validate_label_p_too_low():
    result = validator.validate_label(LabelConfig(name="x", p=-0.1))
    assert isinstance(result, Err)
    assert isinstance(result.error, ValidationError)
    assert result.error.field == "p"


def test_validate_label_p_too_high():
    result = validator.validate_label(LabelConfig(name="x", p=1.1))
    assert isinstance(result, Err)
    assert result.error.field == "p"


# --- validate_source ---

def test_validate_source_valid():
    assert isinstance(validator.validate_source(_src()), Ok)


def test_validate_source_with_multiple_labels():
    labels = {
        "id":    LabelConfig(name="id",    p=1.0),
        "email": LabelConfig(name="email", p=0.9),
    }
    cfg = SourceConfig(name="CRM", key_label="id", p=0.8, labels=labels)
    assert isinstance(validator.validate_source(cfg), Ok)


def test_validate_source_p_too_high():
    result = validator.validate_source(_src(p=1.5))
    assert isinstance(result, Err)
    assert result.error.field == "p"


def test_validate_source_p_too_low():
    result = validator.validate_source(_src(p=-0.1))
    assert isinstance(result, Err)
    assert result.error.field == "p"


def test_validate_source_key_label_not_in_labels():
    labels = {"email": LabelConfig(name="email")}
    cfg = SourceConfig(name="CRM", key_label="missing", labels=labels)
    result = validator.validate_source(cfg)
    assert isinstance(result, Err)
    assert result.error.field == "key_label"


def test_validate_source_label_p_invalid_propagates():
    labels = {
        "id":  LabelConfig(name="id",  p=0.5),
        "bad": LabelConfig(name="bad", p=2.0),
    }
    cfg = SourceConfig(name="CRM", key_label="id", labels=labels)
    result = validator.validate_source(cfg)
    assert isinstance(result, Err)
    assert "bad" in result.error.field


def test_validate_source_returns_ok_value():
    cfg = _src()
    result = validator.validate_source(cfg)
    assert isinstance(result, Ok)
    assert result.value is cfg
