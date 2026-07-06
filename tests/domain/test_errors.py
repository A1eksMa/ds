import dataclasses

from src.domain.errors import (
    AlreadyExists,
    DomainError,
    IntegrityError,
    NotFound,
    ServiceError,
    StorageError,
    ValidationError,
)


def test_not_found_is_frozen():
    e = NotFound(entity="Src", key="crm")
    try:
        e.entity = "other"  # type: ignore[misc]
        assert False
    except (dataclasses.FrozenInstanceError, AttributeError):
        pass


def test_already_exists_fields():
    e = AlreadyExists(entity="Lb", key="email")
    assert e.entity == "Lb"
    assert e.key == "email"


def test_validation_error_fields():
    e = ValidationError(field="p", message="must be 0..1")
    assert e.field == "p"
    assert e.message == "must be 0..1"


def test_storage_error_fields():
    e = StorageError(message="disk full")
    assert e.message == "disk full"


def test_integrity_error_fields():
    e = IntegrityError(message="fk violation")
    assert e.message == "fk violation"


def test_domain_error_union_includes_expected_types():
    import typing
    args = typing.get_args(DomainError)
    assert NotFound in args
    assert AlreadyExists in args
    assert ValidationError in args


def test_service_error_union_includes_storage_error():
    import typing
    args = typing.get_args(ServiceError)
    assert StorageError in args
    assert IntegrityError in args
