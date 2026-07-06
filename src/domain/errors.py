from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class NotFound:
    entity: str
    key: str


@dataclass(frozen=True)
class AlreadyExists:
    entity: str
    key: str


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str


@dataclass(frozen=True)
class StorageError:
    message: str


@dataclass(frozen=True)
class IntegrityError:
    message: str


DomainError = Union[NotFound, AlreadyExists, ValidationError]
ServiceError = Union[NotFound, AlreadyExists, ValidationError, StorageError, IntegrityError]
