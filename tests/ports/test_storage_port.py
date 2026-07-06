import pytest

from src.adapters.inmemory_adapter import InMemoryAdapter
from src.adapters.sqlite_adapter import SQLiteAdapter
from src.ports.storage_port import StoragePort


def test_inmemory_adapter_satisfies_protocol():
    assert isinstance(InMemoryAdapter(), StoragePort)


def test_sqlite_adapter_satisfies_protocol(tmp_path):
    assert isinstance(SQLiteAdapter(str(tmp_path / "test.db")), StoragePort)
