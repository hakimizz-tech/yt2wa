"""Plan the fallback steps used when a file is too big.

Re-encoding does not guarantee a smaller file, so the ladder lists what to
try, in order, until a result fits the size cap.
"""

from __future__ import annotations

from collections.abc import Mapping

from yt2wa.domain.models import RESOLUTION_RUNGS, LadderStep


def rung_for(short_edge: int) -> int:
    """Return the smallest known resolution that fits the short edge."""
    for rung in RESOLUTION_RUNGS:
        if short_edge <= rung:
            return rung
    return RESOLUTION_RUNGS[-1]


def compute_video_bitrate_k(
    cap_bytes: int,
    duration_s: float,
    audio_k: int,
    safety: float = 0.95,
) -> int:
    """Return the video bitrate (kbit/s) that keeps a file under the cap."""
    if duration_s <= 0:
        raise ValueError("duration must be positive")
    total_bits = cap_bytes * 8 * safety
    audio_bits = audio_k * 1000 * duration_s
    video_bps = (total_bits - audio_bits) / duration_s
    return max(0, int(video_bps // 1000))


def plan_size_ladder(
    start: int,
    floor: int,
    duration_s: float,
    cap_bytes: int | None,
    audio_k: int,
    min_bitrates: Mapping[int, int],
) -> tuple[LadderStep, ...]:
    """List the attempts to make, from best quality to smallest.

    Step 1 is a quality based encode. The next steps aim for a bitrate
    that fits the cap, first at the starting resolution and then one
    resolution rung lower at a time, down to the floor. A rung is skipped
    when the bitrate it would get is too low to look acceptable.
    """
    steps = [LadderStep("crf", start)]
    if cap_bytes is None or duration_s <= 0:
        return tuple(steps)

    lower = [r for r in reversed(RESOLUTION_RUNGS) if floor <= r < start]
    added = False
    for resolution in [start, *lower]:
        safety = 0.85 if added else 0.95
        bitrate = compute_video_bitrate_k(
            cap_bytes, duration_s, audio_k, safety
        )
        minimum = min_bitrates.get(rung_for(resolution), 0)
        if bitrate > 0 and bitrate >= minimum:
            steps.append(LadderStep("bitrate", resolution, bitrate))
            added = True
    return tuple(steps)
