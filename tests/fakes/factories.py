"""Helpers that build test data."""

from __future__ import annotations

from dataclasses import replace

from yt2wa.domain.models import StreamFacts

MP4 = "mov,mp4,m4a,3gp,3g2,mj2"


def make_facts(**overrides: object) -> StreamFacts:
    """Return facts for a file that already matches the profile."""
    base = StreamFacts(
        container=MP4,
        vcodec="h264",
        vprofile="High",
        vlevel=31,
        pix_fmt="yuv420p",
        width=854,
        height=480,
        fps=30.0,
        rotation=0,
        acodec="aac",
        aprofile="LC",
        channels=2,
        sample_rate=48000,
        size_bytes=5 * 1024 * 1024,
        duration_s=60.0,
        faststart=True,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]
