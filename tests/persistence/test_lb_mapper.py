from src.domain.entities import Lb, LbId
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok
from src.persistence.mappers import lb_mapper
from src.persistence.records.lb_record import LbRecord


def _record(**kwargs) -> LbRecord:
    defaults = dict(lb_id=1, name="email", p=0.5, description=None)
    return LbRecord(**{**defaults, **kwargs})


def test_record_to_domain_ok():
    result = lb_mapper.record_to_domain(_record())
    assert isinstance(result, Ok)
    lb = result.value
    assert lb.lb_id == LbId(1)
    assert lb.name == "email"
    assert lb.p == 0.5


def test_record_to_domain_with_description():
    result = lb_mapper.record_to_domain(_record(description="Email address"))
    assert isinstance(result, Ok)
    assert result.value.description == "Email address"


def test_record_to_domain_p_invalid_above_one():
    result = lb_mapper.record_to_domain(_record(p=1.5))
    assert isinstance(result, Err)
    assert isinstance(result.error, ValidationError)


def test_record_to_domain_p_invalid_below_zero():
    result = lb_mapper.record_to_domain(_record(p=-0.01))
    assert isinstance(result, Err)


def test_domain_to_record_round_trip():
    record = _record(p=0.7, description="Phone number")
    lb = lb_mapper.record_to_domain(record).value
    back = lb_mapper.domain_to_record(lb)
    assert back == record


def test_domain_to_record_preserves_all_fields():
    lb = Lb(lb_id=LbId(5), name="phone", p=0.8, description="Phone")
    record = lb_mapper.domain_to_record(lb)
    assert record.lb_id == 5
    assert record.name == "phone"
    assert record.p == 0.8
    assert record.description == "Phone"
