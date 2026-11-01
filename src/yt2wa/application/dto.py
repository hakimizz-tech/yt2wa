"""Plain data objects passed between the interface and the use cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yt2wa.domain.models import (
    ComplianceReport,
    Method,
    ProgressCallback,
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
