"""Entities and value objects shared by every layer.

All of them are immutable and free of I/O.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# Resolution value that means "the highest quality available".
BEST_RESOLUTION = 0

# Short-edge sizes the tool understands, smallest first.
RESOLUTION_RUNGS = (144, 240, 360, 480, 720, 1080)


class Target(StrEnum):
    """What the output file is meant for."""

    ORIGINAL = "original"
    CHAT = "chat"
    STATUS = "status"

    @property
    def is_shareable(self) -> bool:
        """Return True when the file must suit WhatsApp."""
        return self is not Target.ORIGINAL


class SourceKind(StrEnum):
    """The kind of YouTube link we were given."""

    VIDEO = "video"
    SHORT = "short"
    UNSUPPORTED = "unsupported"


class Method(StrEnum):
    """How the output file was produced."""

    DOWNLOAD = "download"
    REMUX = "remux"
    TRANSCODE = "transcode"


class Severity(StrEnum):
    """How serious a failed check is."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class SourceRef:
    """A classified YouTube link."""

    url: str
    kind: SourceKind
    video_id: str | None = None


@dataclass(frozen=True)
class SourceMetadata:
    """Basic facts about a video, known before downloading it."""

    video_id: str
    title: str
    duration_s: float
    uploader: str | None = None


@dataclass(frozen=True)
class FormatChoice:
    """How yt-dlp should pick the streams to download."""

    selector: str
    sort: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class StreamFacts:
    """What ffprobe tells us about a media file."""

    container: str
    vcodec: str | None
    vprofile: str | None
    vlevel: int | None
    pix_fmt: str | None
    width: int
    height: int
    fps: float
    rotation: int
    acodec: str | None
    aprofile: str | None
    channels: int | None
    sample_rate: int | None
    size_bytes: int
    duration_s: float
    faststart: bool | None

    @property
    def has_audio(self) -> bool:
        """Return True when the file has an audio stream."""
        return self.acodec is not None

    @property
    def display_size(self) -> tuple[int, int]:
        """Return (width, height) as a viewer sees it after rotation."""
        if self.rotation in (90, 270):
            return self.height, self.width
        return self.width, self.height

    @property
    def short_edge(self) -> int:
        """Return the shorter side of the displayed picture."""
        return min(self.display_size)

    @property
    def aspect(self) -> float:
        """Return displayed width divided by height."""
        width, height = self.display_size
        return width / height if height else 0.0


@dataclass(frozen=True)
class Progress:
    """A progress update from a long running step."""

    stage: str
    fraction: float | None = None


ProgressCallback = Callable[[Progress], None]


def ignore_progress(progress: Progress) -> None:
    """Accept a progress update and do nothing with it."""


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one compliance check."""

    name: str
    expected: str
    actual: str
    passed: bool
    severity: Severity = Severity.ERROR


@dataclass(frozen=True)
class ComplianceReport:
    """All check results for one file."""

    results: tuple[CheckResult, ...]

    @property
    def failed(self) -> tuple[CheckResult, ...]:
        """Return every check that did not pass."""
        return tuple(r for r in self.results if not r.passed)

    @property
    def errors(self) -> tuple[CheckResult, ...]:
        """Return failed checks that must be fixed."""
        return tuple(r for r in self.failed if r.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[CheckResult, ...]:
        """Return failed checks that are only advice."""
        return tuple(
            r for r in self.failed if r.severity is Severity.WARNING
        )

    @property
    def ok(self) -> bool:
        """Return True when no error-level check failed."""
        return not self.errors


@dataclass(frozen=True)
class PathDecision:
    """Whether to copy the streams or re-encode them."""

    method: Method
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class LadderStep:
    """One attempt in the size guard ladder."""

    kind: str  # "crf" or "bitrate"
    resolution: int
    video_bitrate_k: int | None = None


@dataclass(frozen=True)
class Candidate:
    """A finished output file together with its compliance report."""

    path: Path
    report: ComplianceReport
    size_bytes: int
    method: Method


@dataclass(frozen=True)
class ConversionResult:
    """What the user gets back from a conversion."""

    output: Path
    target: Target
    method: Method
    title: str
    requested_resolution: int
    effective_resolution: int
    size_bytes: int
    report: ComplianceReport | None
    warnings: tuple[str, ...] = ()
    source_kept: Path | None = None


@dataclass(frozen=True)
class DryRunPlan:
    """A description of what a run would do."""

    lines: tuple[str, ...]
