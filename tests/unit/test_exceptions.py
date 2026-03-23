"""Tests for the exception hierarchy."""

from __future__ import annotations

import pytest

from strands_compose.exceptions import (
    CircularDependencyError,
    ConfigurationError,
    ImportResolutionError,
    SchemaValidationError,
    UnresolvedReferenceError,
)


class TestExceptionHierarchy:
    """Verify that all custom exceptions form the correct inheritance chain."""

    @pytest.mark.parametrize(
        ("exc_cls", "parent_cls"),
        [
            (ConfigurationError, ValueError),
            (SchemaValidationError, ConfigurationError),
            (UnresolvedReferenceError, ConfigurationError),
            (CircularDependencyError, ConfigurationError),
            (ImportResolutionError, ConfigurationError),
        ],
        ids=[
            "ConfigurationError<-ValueError",
            "SchemaValidationError<-ConfigurationError",
            "UnresolvedReferenceError<-ConfigurationError",
            "CircularDependencyError<-ConfigurationError",
            "ImportResolutionError<-ConfigurationError",
        ],
    )
    def test_exception_hierarchy(self, exc_cls, parent_cls):
        """Each exception class is a subclass of its expected parent."""
        assert issubclass(exc_cls, parent_cls)

    def test_except_configuration_error_catches_subclasses(self):
        """Existing ``except ConfigurationError`` handlers catch all subclasses."""
        for exc_cls in (
            SchemaValidationError,
            UnresolvedReferenceError,
            CircularDependencyError,
            ImportResolutionError,
        ):
            with pytest.raises(ConfigurationError):
                raise exc_cls("test")

    def test_except_value_error_catches_all(self):
        """Existing ``except ValueError`` handlers catch all subclasses."""
        for exc_cls in (
            ConfigurationError,
            SchemaValidationError,
            UnresolvedReferenceError,
            CircularDependencyError,
            ImportResolutionError,
        ):
            with pytest.raises(ValueError):
                raise exc_cls("test")

    def test_specific_catch_does_not_catch_siblings(self):
        """An ``UnresolvedReferenceError`` should not be caught by ``except SchemaValidationError``."""
        with pytest.raises(UnresolvedReferenceError):
            try:
                raise UnresolvedReferenceError("bad ref")
            except SchemaValidationError:
                pytest.fail("Should not catch sibling exception")

    @pytest.mark.parametrize(
        ("exc_cls", "msg"),
        [
            (ConfigurationError, "config broken"),
            (SchemaValidationError, "bad field 'x'"),
            (UnresolvedReferenceError, "ref not found"),
            (CircularDependencyError, "cycle detected"),
            (ImportResolutionError, "import failed"),
        ],
    )
    def test_exception_preserves_message(self, exc_cls, msg):
        """All exception classes preserve their message in str()."""
        exc = exc_cls(msg)
        assert str(exc) == msg
