"""Fakes and factories for the v0.3 tests (audio and search)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from yt2wa.domain.errors import DomainError
from yt2wa.domain.models import (
    CandidateOrigin,
    SearchCandidate,
    SearchKind,
    SearchProviderName,
    StreamFacts,
)

MP4 = "mov,mp4,m4a,3gp,3g2,mj2"


def make_audio_facts(**overrides: object) -> StreamFacts:
    """Return facts for an audio file that already matches the profile."""
    base = StreamFacts(
        container=MP4,
        vcodec=None,
        vprofile=None,
        vlevel=None,
        pix_fmt=None,
        width=0,
        height=0,
        fps=0.0,
        rotation=0,
        acodec="aac",
        aprofile="LC",
        channels=2,
        sample_rate=44100,
        size_bytes=3 * 1024 * 1024,
        duration_s=200.0,
        faststart=True,
        abitrate_k=128,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


class FakeAudioProbe:
    """Returns the source facts, or sane audio facts for candidates."""

    def __init__(self, source: StreamFacts) -> None:
        self._source = source

    def inspect(self, path: Path) -> StreamFacts:
        if path.name.startswith("candidate"):
            # The bitrate of a fake file is unknown, so it always passes.
            return make_audio_facts(
                size_bytes=path.stat().st_size, abitrate_k=None
            )
        return self._source


def make_candidate(
    video_id: str = "aaaaaaaaaaa",
    title: str = "Artist - Song",
    channel: str = "Artist",
    duration_s: float = 200.0,
    view_count: int | None = 1_000_000,
    position: int = 0,
    origin: CandidateOrigin = CandidateOrigin.UNKNOWN,
    provider: SearchProviderName = SearchProviderName.YTSEARCH,
    artists: tuple[str, ...] = (),
) -> SearchCandidate:
    """Build a search candidate with sensible defaults."""
    return SearchCandidate(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        channel=channel,
        duration_s=duration_s,
        view_count=view_count,
        position=position,
        origin=origin,
        provider=provider,
        artists=artists,
    )


class FakeSearchProvider:
    """A search method that returns fixed results or raises an error."""

    def __init__(
        self,
        results: list[SearchCandidate] | None = None,
        error: DomainError | None = None,
    ) -> None:
        self._results = results or []
        self._error = error
        self.calls: list[tuple[str, SearchKind, int]] = []

    def search(
        self, query: str, kind: SearchKind, limit: int
    ) -> list[SearchCandidate]:
        self.calls.append((query, kind, limit))
        if self._error is not None:
            raise self._error
        return list(self._results)
