from src.domain.entities import LbId, Src, SrcId
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok
from src.persistence.mappers import src_mapper
from src.persistence.records.src_record import SrcRecord


def _record(**kwargs) -> SrcRecord:
    defaults = dict(src_id=1, name="CRM", p=0.9, key_label=2, description=None)
    return SrcRecord(**{**defaults, **kwargs})


def test_record_to_domain_ok():
    result = src_mapper.record_to_domain(_record())
    assert isinstance(result, Ok)
    src = result.value
    assert src.src_id == SrcId(1)
    assert src.name == "CRM"
    assert src.p == 0.9
    assert src.key_label == LbId(2)
    assert src.description is None


def test_record_to_domain_key_label_none_before_bootstrap():
    result = src_mapper.record_to_domain(_record(key_label=None))
    assert isinstance(result, Ok)
    assert result.value.key_label is None


def test_record_to_domain_with_description():
    result = src_mapper.record_to_domain(_record(description="Customer system"))
    assert isinstance(result, Ok)
    assert result.value.description == "Customer system"


def test_record_to_domain_p_zero_is_valid():
    assert isinstance(src_mapper.record_to_domain(_record(p=0.0)), Ok)


def test_record_to_domain_p_one_is_valid():
    assert isinstance(src_mapper.record_to_domain(_record(p=1.0)), Ok)


def test_record_to_domain_p_above_one_returns_err():
    result = src_mapper.record_to_domain(_record(p=1.1))
    assert isinstance(result, Err)
    assert isinstance(result.error, ValidationError)
    assert result.error.field == "p"


def test_record_to_domain_p_below_zero_returns_err():
    result = src_mapper.record_to_domain(_record(p=-0.1))
    assert isinstance(result, Err)
    assert isinstance(result.error, ValidationError)


def test_domain_to_record_round_trip():
    record = _record(description="ERP")
    src = src_mapper.record_to_domain(record).value
    back = src_mapper.domain_to_record(src)
    assert back == record


def test_domain_to_record_round_trip_key_label_none():
    record = _record(key_label=None)
    src = src_mapper.record_to_domain(record).value
    back = src_mapper.domain_to_record(src)
    assert back == record


def test_domain_to_record_preserves_all_fields():
    src = Src(src_id=SrcId(7), name="ERP", p=0.95, key_label=LbId(3), description="ERP system")
    record = src_mapper.domain_to_record(src)
    assert record.src_id == 7
    assert record.name == "ERP"
    assert record.p == 0.95
    assert record.key_label == 3
    assert record.description == "ERP system"
