"""Plain data objects passed between the interface and the use cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yt2wa.domain.audio_profile import AudioProfile
from yt2wa.domain.models import (
    AudioFormat,
    ComplianceReport,
    ConversionResult,
    MediaKind,
    Method,
    ProgressCallback,
    SearchKind,
    SearchProviderName,
    SearchResult,
    SourceMetadata,
    SourceRef,
    StreamFacts,
    Target,
)
from yt2wa.domain.profile import CompatProfile


@dataclass(frozen=True)
class ConvertRequest:
    """What the user asked for."""

    url: str
    target: Target
    resolution: int
    output_dir: Path
    max_size_mb: int | None = None
    keep_source: bool = False
    dry_run: bool = False
    media: MediaKind = MediaKind.VIDEO
    audio_format: AudioFormat = AudioFormat.M4A
    audio_bitrate_k: int | None = None


@dataclass(frozen=True)
class JobContext:
    """Everything a strategy needs to do its work."""

    request: ConvertRequest
    ref: SourceRef
    metadata: SourceMetadata
    job_dir: Path
    profile: CompatProfile
    size_cap_bytes: int | None
    on_progress: ProgressCallback
    audio_profile: AudioProfile | None = None


@dataclass(frozen=True)
class StrategyOutput:
    """What a strategy hands back before the file is published."""

    path: Path
    method: Method
    facts: StreamFacts
    report: ComplianceReport | None
    warnings: tuple[str, ...] = ()
    source: Path | None = None


@dataclass(frozen=True)
class VerifyRequest:
    """A request to check an existing file."""

    path: Path
    target: Target


@dataclass(frozen=True)
class VerifyResult:
    """The outcome of checking a file."""

    path: Path
    target: Target
    facts: StreamFacts
    report: ComplianceReport
    media: MediaKind = MediaKind.VIDEO


@dataclass(frozen=True)
class SearchRequest:
    """What the user asked a search to do."""

    query: str
    kind: SearchKind = SearchKind.ANY
    limit: int = 5
    provider: SearchProviderName | None = None  # None means automatic.
    detail: bool = False
    min_confidence: float = 0.6
    download: ConvertRequest | None = None
    pick: int | None = None


@dataclass(frozen=True)
class SearchOutcome:
    """Everything a search produced."""

    result: SearchResult
    detail: SourceMetadata | None = None
    conversion: ConversionResult | None = None
    notes: tuple[str, ...] = ()
