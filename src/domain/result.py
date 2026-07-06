from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

    def and_then(self, f: Callable[[T], Ok[U] | Err[E]]) -> Ok[U] | Err[E]:
        return f(self.value)

    def map(self, f: Callable[[T], U]) -> Ok[U]:
        return Ok(f(self.value))


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

    def and_then(self, f: object) -> Err[E]:
        return self

    def map(self, f: object) -> Err[E]:
        return self
