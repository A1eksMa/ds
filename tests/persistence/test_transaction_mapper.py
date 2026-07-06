from src.domain.entities import (
    ActId, CntId, IdId, LbId, SrcId, Transaction, TransactionInput, ValId,
)
from src.domain.errors import ValidationError
from src.domain.result import Err, Ok
from src.persistence.mappers import transaction_mapper
from src.persistence.records.transaction_record import TransactionRecord

_TS = 1_700_000_000.0


def _record(**kwargs) -> TransactionRecord:
    defaults = dict(cnt=1, act=1, dt=_TS, src=2, lb=3, id=4, p=1.0, val=5)
    return TransactionRecord(**{**defaults, **kwargs})


def test_record_to_domain_ok():
    result = transaction_mapper.record_to_domain(_record())
    assert isinstance(result, Ok)
    txn = result.value
    assert txn.cnt == CntId(1)
    assert txn.act == ActId(1)
    assert txn.dt == _TS
    assert txn.src == SrcId(2)
    assert txn.lb == LbId(3)
    assert txn.id == IdId(4)
    assert txn.p == 1.0
    assert txn.val == ValId(5)


def test_record_to_domain_val_none_delete_semantics():
    result = transaction_mapper.record_to_domain(_record(val=ValId(0)))
    assert isinstance(result, Ok)
    assert result.value.val == ValId(0)


def test_record_to_domain_p_invalid():
    result = transaction_mapper.record_to_domain(_record(p=1.5))
    assert isinstance(result, Err)
    assert isinstance(result.error, ValidationError)


def test_domain_to_record_round_trip():
    record = _record()
    txn = transaction_mapper.record_to_domain(record).value
    back = transaction_mapper.domain_to_record(txn)
    assert back == record


def test_domain_to_record_val_none():
    record = _record(val=ValId(0))
    txn = transaction_mapper.record_to_domain(record).value
    back = transaction_mapper.domain_to_record(txn)
    assert back.val == ValId(0)


def test_input_to_row_fills_cnt():
    txn_input = TransactionInput(
        act=ActId(1), dt=_TS, src=SrcId(2),
        lb=LbId(3), id=IdId(4), p=0.9, val=ValId(5),
    )
    row = transaction_mapper.input_to_row(txn_input, CntId(99))
    assert row.cnt == 99
    assert row.act == 1
    assert row.src == 2
    assert row.val == 5


def test_input_to_row_delete_semantics():
    txn_input = TransactionInput(
        act=ActId(4), dt=_TS, src=SrcId(1),
        lb=LbId(1), id=IdId(1), p=1.0, val=ValId(0),
    )
    row = transaction_mapper.input_to_row(txn_input, CntId(10))
    assert row.val == ValId(0)
