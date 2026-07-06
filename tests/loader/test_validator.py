from src.config.models import LabelConfig, SourceConfig
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok
from src.loader import validator


def _cfg(key_label="id"):
    return SourceConfig(
        name="S", key_label=key_label,
        labels={key_label: LabelConfig(name=key_label)},
    )


def test_validate_table_valid():
    data = {"id": ["1", "2"], "email": ["a@b.com", "c@d.com"]}
    assert isinstance(validator.validate_table(data, _cfg()), Ok)


def test_validate_table_key_label_only():
    data = {"id": ["1", "2"]}
    assert isinstance(validator.validate_table(data, _cfg()), Ok)


def test_validate_table_empty_rows():
    data = {"id": [], "email": []}
    assert isinstance(validator.validate_table(data, _cfg()), Ok)


def test_validate_table_null_value_in_non_key_column_is_allowed():
    data = {"id": ["1"], "email": [None]}
    assert isinstance(validator.validate_table(data, _cfg()), Ok)


def test_validate_table_not_dict():
    result = validator.validate_table(["not", "a", "dict"], _cfg())
    assert isinstance(result, Err)
    assert result.error.field == "data"


def test_validate_table_missing_key_label():
    data = {"email": ["a@b.com"]}
    result = validator.validate_table(data, _cfg("id"))
    assert isinstance(result, Err)
    assert result.error.field == "id"


def test_validate_table_unequal_column_lengths():
    data = {"id": ["1", "2"], "email": ["a@b.com"]}
    result = validator.validate_table(data, _cfg())
    assert isinstance(result, Err)
    assert result.error.field == "columns"


def test_validate_table_null_in_key_label():
    data = {"id": ["1", None, "3"], "email": ["a", "b", "c"]}
    result = validator.validate_table(data, _cfg())
    assert isinstance(result, Err)
    assert result.error.field == "id"


def test_validate_table_column_not_a_list():
    data = {"id": "not_a_list", "email": ["a"]}
    result = validator.validate_table(data, _cfg())
    assert isinstance(result, Err)
    assert isinstance(result.error, ValidationError)


def test_validate_table_duplicate_key_values():
    data = {"id": ["1", "2", "1"], "email": ["a", "b", "c"]}
    result = validator.validate_table(data, _cfg())
    assert isinstance(result, Err)
    assert result.error.field == "id"


def test_validate_table_duplicate_int_key_values():
    data = {"id": [1, 2, 1], "email": ["a", "b", "c"]}
    result = validator.validate_table(data, _cfg())
    assert isinstance(result, Err)
    assert result.error.field == "id"


def test_validate_table_unique_key_values_ok():
    data = {"id": ["1", "2", "3"], "email": ["a", "b", "c"]}
    assert isinstance(validator.validate_table(data, _cfg()), Ok)
