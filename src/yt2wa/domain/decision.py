"""Decide how to turn a download into a shareable file."""

from __future__ import annotations

from collections.abc import Sequence

from yt2wa.domain import compliance as c
from yt2wa.domain.models import (
    Candidate,
    ComplianceReport,
    Method,
    PathDecision,
)

# Failing any of these means the streams themselves must be re-encoded.
_REENCODE = frozenset(
    {
        c.VIDEO_CODEC,
        c.VIDEO_PROFILE,
        c.VIDEO_LEVEL,
        c.PIXEL_FORMAT,
        c.FRAME_RATE,
        c.RESOLUTION,
        c.ORIENTATION,
        c.AUDIO_CODEC,
        c.AUDIO_PROFILE,
        c.AUDIO_CHANNELS,
        c.SAMPLE_RATE,
    }
)

# These can be fixed by copying the streams into a new MP4.
_REMUX = frozenset({c.CONTAINER, c.FASTSTART})


def decide_path(report: ComplianceReport) -> PathDecision:
    """Choose between a lossless remux and a full transcode."""
    failed = [result.name for result in report.errors]
    reencode = [name for name in failed if name in _REENCODE]
    if reencode:
        return PathDecision(Method.TRANSCODE, tuple(reencode))
    if c.FILE_SIZE in failed:
        # Copying the streams cannot make the file smaller.
        return PathDecision(Method.TRANSCODE, ("file is over the size cap",))
    if failed:
        return PathDecision(Method.REMUX, tuple(failed))
    return PathDecision(Method.REMUX, ("already compliant",))


def choose_best_candidate(candidates: Sequence[Candidate]) -> Candidate | None:
    """Return the smallest compliant candidate, or None."""
    compliant = [cand for cand in candidates if cand.report.ok]
    if not compliant:
        return None
    return min(compliant, key=lambda cand: cand.size_bytes)
