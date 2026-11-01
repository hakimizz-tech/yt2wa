"""Fake adapters used by the application tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fakes.factories import make_facts
from yt2wa.domain.models import (
    FormatChoice,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
    StreamFacts,
)


class FakeDownloader:
    """Pretends to download a video."""

    def __init__(self, duration_s: float = 60.0) -> None:
        self._duration = duration_s
        self.choices: list[FormatChoice] = []

    def probe(self, ref: SourceRef) -> SourceMetadata:
        return SourceMetadata("abcdefghijk", "My Clip", self._duration)

    def download(
        self,
        ref: SourceRef,
        choice: FormatChoice,
        dest_dir: Path,
        on_progress: ProgressCallback,
    ) -> Path:
        self.choices.append(choice)
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / "source.mkv"
        path.write_bytes(b"source")
        return path


class FakeProbe:
    """Returns the source facts, or sane facts for candidate files."""

    def __init__(self, source: StreamFacts) -> None:
        self._source = source

    def inspect(self, path: Path) -> StreamFacts:
        if path.name.startswith("candidate"):
            return make_facts(size_bytes=path.stat().st_size)
        return self._source


class FakeTranscoder:
    """Writes output files of the sizes it was given, in order."""

    def __init__(self, sizes: Sequence[int]) -> None:
        self._sizes = list(sizes)
        self.calls: list[list[str]] = []

    def run(
        self,
        args: Sequence[str],
        duration_s: float,
        on_progress: ProgressCallback,
    ) -> None:
        self.calls.append(list(args))
        Path(args[-1]).write_bytes(b"0" * self._sizes.pop(0))
