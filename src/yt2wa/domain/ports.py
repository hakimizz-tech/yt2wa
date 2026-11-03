"""Ports: the interfaces the application needs from the outside world."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from yt2wa.domain.models import (
    FormatChoice,
    ProgressCallback,
    SearchCandidate,
    SearchKind,
    SearchProviderName,
    SearchResponse,
    SourceMetadata,
    SourceRef,
    StreamFacts,
)


class Downloader(Protocol):
    """Fetches a video from the web."""

    def probe(self, ref: SourceRef) -> SourceMetadata:
        """Return metadata without downloading the video."""
        ...

    def download(
        self,
        ref: SourceRef,
        choice: FormatChoice,
        dest_dir: Path,
        on_progress: ProgressCallback,
    ) -> Path:
        """Download the video into dest_dir and return the file path."""
        ...


class Transcoder(Protocol):
    """Runs ffmpeg."""

    def run(
        self,
        args: Sequence[str],
        duration_s: float,
        on_progress: ProgressCallback,
    ) -> None:
        """Run ffmpeg with the given argument list."""
        ...


class MediaProbe(Protocol):
    """Reads the real properties of a media file."""

    def inspect(self, path: Path) -> StreamFacts:
        """Return the facts about a file."""
        ...


class Workspace(Protocol):
    """Owns temporary folders and the final output location."""

    def new_job_dir(self) -> Path:
        """Create and return a private scratch folder."""
        ...

    def publish(self, src: Path, dest_dir: Path, final_name: str) -> Path:
        """Move src into dest_dir without ever leaving a partial file."""
        ...

    def cleanup(self, job_dir: Path) -> None:
        """Delete a scratch folder."""
        ...


class SearchProvider(Protocol):
    """One search method. It only finds candidates."""

    def search(
        self, query: str, kind: SearchKind, limit: int
    ) -> list[SearchCandidate]:
        """Return candidates in the order the service listed them."""
        ...


class SearchGateway(Protocol):
    """Runs a search, possibly through several methods in turn."""

    def search(
        self,
        query: str,
        kind: SearchKind,
        limit: int,
        requested: SearchProviderName | None,
    ) -> SearchResponse:
        """Return candidates and how they were found."""
        ...
