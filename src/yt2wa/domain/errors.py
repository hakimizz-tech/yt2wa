"""Domain errors.

Adapters translate third-party exceptions into these at the boundary, so
no outside exception type leaks inward.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every error the tool raises on purpose."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class UsageError(DomainError):
    """The user gave invalid input."""


class ConfigError(UsageError):
    """A setting or profile file is invalid."""


class UnsupportedSourceError(DomainError):
    """The link is not a video or Short we can handle."""


class SourceUnavailableError(DomainError):
    """The video cannot be fetched."""


class PrivateVideoError(SourceUnavailableError):
    """The video is private."""


class RemovedVideoError(SourceUnavailableError):
    """The video was removed or is no longer available."""


class GeoBlockedError(SourceUnavailableError):
    """The video is blocked in this country."""


class AgeRestrictedError(SourceUnavailableError):
    """The video needs a signed-in, age-verified account."""


class NetworkError(DomainError):
    """A network problem survived all retries."""


class DependencyError(DomainError):
    """A required program is missing or too old."""


class MissingBinaryError(DependencyError):
    """An executable could not be found."""


class VersionTooOldError(DependencyError):
    """An installed program is older than we support."""


class TranscodeError(DomainError):
    """ffmpeg or ffprobe failed."""


class ConstraintError(DomainError):
    """The result cannot meet the requested limits."""


class SizeCapError(ConstraintError):
    """The video cannot be made small enough."""


class NonCompliantOutputError(ConstraintError):
    """The finished file fails the compatibility checks."""
