import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.adapters.system_ports import SystemClock


@pytest.fixture
def db() -> InMemoryAdapter:
    return InMemoryAdapter()


@pytest.fixture
def clock() -> SystemClock:
    return SystemClock()


@pytest.fixture
def fixed_ts() -> float:
    return 1_700_000_000.0
