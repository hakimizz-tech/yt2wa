"""Plan the fallback bitrates used when an audio file is too big. Pure."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# Container and tag overhead on top of the raw audio data.
_OVERHEAD = 1.03


@dataclass(frozen=True)
class AudioStep:
    """One audio encode attempt."""

    bitrate_k: int


def estimated_size_bytes(bitrate_k: int, duration_s: float) -> int:
    """Estimate the file size for a bitrate and duration."""
    return int(bitrate_k * 1000 * duration_s / 8 * _OVERHEAD)


def plan_audio_ladder(
    duration_s: float,
    cap_bytes: int | None,
    ladder: Sequence[int],
    min_k: int,
    start_k: int,
) -> tuple[AudioStep, ...]:
    """List bitrates to try, highest first.

    Without a size cap there is a single attempt. Otherwise bitrates that
    cannot fit the cap even in theory are skipped, so no time is wasted
    encoding them. An empty result means nothing can fit.
    """
    if cap_bytes is None or duration_s <= 0:
        # Nothing to fit, so one attempt at the requested bitrate.
        return (AudioStep(start_k),)
    rates = sorted({start_k, *(r for r in ladder if r < start_k)})
    return tuple(
        AudioStep(rate)
        for rate in reversed(rates)
        if rate >= min_k
        and estimated_size_bytes(rate, duration_s) <= cap_bytes
    )
