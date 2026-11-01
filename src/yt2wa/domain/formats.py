"""Rules for choosing which streams to download."""

from __future__ import annotations

from yt2wa.domain.errors import UsageError
from yt2wa.domain.models import (
    BEST_RESOLUTION,
    RESOLUTION_RUNGS,
    FormatChoice,
    Target,
)


def parse_resolution(text: str) -> int:
    """Turn '480', '480p' or 'best' into a resolution value."""
    cleaned = text.strip().lower()
    if cleaned == "best":
        return BEST_RESOLUTION
    cleaned = cleaned.removesuffix("p")
    if cleaned.isdigit() and int(cleaned) in RESOLUTION_RUNGS:
        return int(cleaned)
    choices = ", ".join(str(rung) for rung in RESOLUTION_RUNGS)
    raise UsageError(
        f"Unsupported resolution '{text}'.",
        hint=f"Use one of: {choices}, best.",
    )


def short_edge_cap(
    target: Target, requested: int, max_short_edge: int
) -> int | None:
    """Return the largest short edge allowed, or None for no limit.

    Shareable targets are always limited by the profile maximum.
    """
    if target is Target.ORIGINAL:
        return None if requested == BEST_RESOLUTION else requested
    if requested == BEST_RESOLUTION:
        return max_short_edge
    return min(requested, max_short_edge)


def build_format_selector(
    target: Target, requested: int, max_short_edge: int = 1080
) -> FormatChoice:
    """Build the yt-dlp format choice for a target and resolution.

    yt-dlp's ``res`` sort key is the short edge, so portrait Shorts and
    landscape videos are handled the same way. It prefers the largest
    stream at or below the limit, then H.264 video and AAC audio.
    """
    cap = short_edge_cap(target, requested, max_short_edge)
    res_key = "res" if cap is None else f"res:{cap}"
    return FormatChoice(
        selector="bv*+ba/b",
        sort=(res_key, "vcodec:h264", "acodec:aac"),
    )
