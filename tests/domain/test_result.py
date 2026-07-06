from src.domain.result import Err, Ok


def test_ok_and_then_calls_f():
    assert Ok(1).and_then(lambda x: Ok(x + 1)) == Ok(2)


def test_ok_and_then_propagates_err_from_f():
    assert Ok(1).and_then(lambda x: Err("fail")) == Err("fail")


def test_err_and_then_skips_f():
    called = []
    result = Err("fail").and_then(lambda x: called.append(x) or Ok(x))
    assert result == Err("fail")
    assert called == []


def test_ok_map_transforms_value():
    assert Ok(2).map(lambda x: x * 3) == Ok(6)


def test_err_map_skips_f():
    assert Err("fail").map(lambda x: x * 3) == Err("fail")


def test_chain_ok_ok_ok():
    result = (
        Ok(1)
        .and_then(lambda x: Ok(x + 1))
        .and_then(lambda x: Ok(x * 10))
        .map(str)
    )
    assert result == Ok("20")


def test_chain_short_circuits_on_first_err():
    steps = []
    result = (
        Ok(1)
        .and_then(lambda x: steps.append("a") or Err("stop"))
        .and_then(lambda x: steps.append("b") or Ok(x))
    )
    assert result == Err("stop")
    assert steps == ["a"]


def test_ok_is_frozen():
    import dataclasses
    assert dataclasses.is_dataclass(Ok)
    o = Ok(42)
    try:
        o.value = 99  # type: ignore[misc]
        assert False, "should be immutable"
    except (dataclasses.FrozenInstanceError, AttributeError):
        pass


def test_err_is_frozen():
    import dataclasses
    e = Err("x")
    try:
        e.error = "y"  # type: ignore[misc]
        assert False, "should be immutable"
    except (dataclasses.FrozenInstanceError, AttributeError):
        pass
