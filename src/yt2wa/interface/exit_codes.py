"""Exit codes and the mapping from errors to codes."""

from __future__ import annotations

from enum import IntEnum

from yt2wa.domain.errors import (
    ConstraintError,
    DependencyError,
    DomainError,
    NetworkError,
    NotFoundError,
    SourceUnavailableError,
    TranscodeError,
    UnsupportedSourceError,
    UsageError,
)


class ExitCode(IntEnum):
    """Process exit codes."""

    OK = 0
    GENERAL = 1
    USAGE = 2
    UNSUPPORTED = 3
    UNAVAILABLE = 4
    NETWORK = 5
    DEPENDENCY = 6
    TRANSCODE = 7
    CONSTRAINT = 8
    NOT_FOUND = 9
    INTERRUPTED = 130


_CODES: tuple[tuple[type[DomainError], ExitCode], ...] = (
    (UsageError, ExitCode.USAGE),
    (UnsupportedSourceError, ExitCode.UNSUPPORTED),
    (SourceUnavailableError, ExitCode.UNAVAILABLE),
    (NetworkError, ExitCode.NETWORK),
    (DependencyError, ExitCode.DEPENDENCY),
    (TranscodeError, ExitCode.TRANSCODE),
    (ConstraintError, ExitCode.CONSTRAINT),
    (NotFoundError, ExitCode.NOT_FOUND),
)


def map_exception_to_exit_code(exc: Exception) -> ExitCode:
    """Return the exit code for an error."""
    for error_type, code in _CODES:
        if isinstance(exc, error_type):
            return code
    return ExitCode.GENERAL
