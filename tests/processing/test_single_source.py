from src.domain.entities import ActId, CntId, IdId, LbId, SrcId, Transaction, ValId
from src.processing.single_source import fold_state

_SRC = SrcId(1)
_LB = LbId(1)
_ID = IdId(1)
_ACT = ActId(1)
_TS = 1_700_000_000.0


def _txn(cnt, val, src=_SRC, lb=_LB, id_=_ID, dt=_TS, p=1.0):
    return Transaction(
        cnt=CntId(cnt), act=_ACT, dt=dt, src=src, lb=lb, id=id_, p=p, val=ValId(val),
    )


def test_fold_state_empty_input_returns_empty_state():
    assert fold_state([]) == {}


def test_fold_state_single_transaction():
    txn = _txn(cnt=1, val=1)
    state = fold_state([txn])
    assert state == {(_SRC, _LB, _ID): ValId(1)}


def test_fold_state_later_cnt_overwrites_earlier_for_same_key():
    older = _txn(cnt=1, val=1)
    newer = _txn(cnt=2, val=2)
    state = fold_state([older, newer])
    assert state[(_SRC, _LB, _ID)] == ValId(2)


def test_fold_state_is_independent_of_input_order():
    older = _txn(cnt=1, val=1)
    newer = _txn(cnt=2, val=2)
    # cnt (not list position, not dt) decides the winner.
    state = fold_state([newer, older])
    assert state[(_SRC, _LB, _ID)] == ValId(2)


def test_fold_state_winner_decided_by_cnt_not_dt():
    # A misleading dt must not override the cnt-based decision.
    earlier_cnt_later_dt = _txn(cnt=1, val=1, dt=_TS + 100)
    later_cnt_earlier_dt = _txn(cnt=2, val=2, dt=_TS)
    state = fold_state([earlier_cnt_later_dt, later_cnt_earlier_dt])
    assert state[(_SRC, _LB, _ID)] == ValId(2)


def test_fold_state_delete_keeps_key_with_zero_sentinel():
    post = _txn(cnt=1, val=1)
    delete = _txn(cnt=2, val=0)
    state = fold_state([post, delete])
    assert (_SRC, _LB, _ID) in state
    assert state[(_SRC, _LB, _ID)] == ValId(0)


def test_fold_state_keeps_distinct_keys_independent():
    a = _txn(cnt=1, val=1, id_=IdId(1))
    b = _txn(cnt=2, val=2, id_=IdId(2))
    state = fold_state([a, b])
    assert state == {
        (_SRC, _LB, IdId(1)): ValId(1),
        (_SRC, _LB, IdId(2)): ValId(2),
    }


def test_fold_state_distinguishes_by_full_key_not_just_id():
    from_src_a = _txn(cnt=1, val=1, src=SrcId(1))
    from_src_b = _txn(cnt=2, val=2, src=SrcId(2))
    state = fold_state([from_src_a, from_src_b])
    assert len(state) == 2
