"""Check a file against the compatibility profile.

``check_compliance`` is the single source of truth. It decides whether a
download can simply be copied, verifies the finished output and powers the
``verify`` command.
"""

from __future__ import annotations

from yt2wa.domain.models import (
    CheckResult,
    ComplianceReport,
    Severity,
    StreamFacts,
)
from yt2wa.domain.profile import CompatProfile

CONTAINER = "container"
VIDEO_CODEC = "video_codec"
VIDEO_PROFILE = "video_profile"
VIDEO_LEVEL = "video_level"
PIXEL_FORMAT = "pixel_format"
FRAME_RATE = "frame_rate"
RESOLUTION = "resolution"
ASPECT_PRESERVED = "aspect_preserved"
ASPECT_RATIO = "aspect_ratio"
ORIENTATION = "orientation"
AUDIO_PRESENT = "audio_present"
AUDIO_CODEC = "audio_codec"
AUDIO_PROFILE = "audio_profile"
AUDIO_CHANNELS = "audio_channels"
SAMPLE_RATE = "sample_rate"
FASTSTART = "faststart"
FILE_SIZE = "file_size"
DURATION = "duration"

_ASPECT_TOLERANCE = 0.03


def _check(
    name: str,
    expected: object,
    actual: object,
    passed: bool,
    severity: Severity = Severity.ERROR,
) -> CheckResult:
    """Build a check result, turning values into text."""
    return CheckResult(name, str(expected), str(actual), passed, severity)


def _video_checks(
    facts: StreamFacts, profile: CompatProfile, short_cap: int
) -> list[CheckResult]:
    """Check container, video codec and picture size."""
    tokens = {part.strip() for part in facts.container.split(",")}
    width, height = facts.display_size
    level = facts.vlevel
    return [
        _check(CONTAINER, "mp4", facts.container, "mp4" in tokens),
        _check(
            VIDEO_CODEC, "h264", facts.vcodec or "none", facts.vcodec == "h264"
        ),
        _check(
            VIDEO_PROFILE,
            " / ".join(profile.allowed_h264_profiles),
            facts.vprofile or "none",
            facts.vprofile in profile.allowed_h264_profiles,
        ),
        _check(
            VIDEO_LEVEL,
            f"<= {profile.max_h264_level}",
            "unknown" if level is None else level,
            level is None or level <= profile.max_h264_level,
        ),
        _check(
            PIXEL_FORMAT,
            "yuv420p",
            facts.pix_fmt or "none",
            facts.pix_fmt == "yuv420p",
        ),
        _check(
            FRAME_RATE,
            f"<= {profile.max_fps:g} fps",
            f"{facts.fps:.2f} fps",
            facts.fps <= profile.max_fps + 0.05,
        ),
        _check(
            RESOLUTION,
            f"short edge <= {short_cap}, long edge <= "
            f"{profile.max_long_edge}",
            f"{width}x{height}",
            min(width, height) <= short_cap
            and max(width, height) <= profile.max_long_edge,
        ),
        _check(
            ORIENTATION,
            "no rotation metadata",
            f"{facts.rotation} degrees",
            facts.rotation == 0,
        ),
    ]


def _audio_checks(
    facts: StreamFacts, profile: CompatProfile
) -> list[CheckResult]:
    """Check the audio stream, or warn when there is none."""
    if not facts.has_audio:
        return [
            _check(
                AUDIO_PRESENT,
                "an audio stream",
                "none",
                False,
                Severity.WARNING,
            )
        ]
    rates = " or ".join(str(rate) for rate in profile.sample_rates)
    return [
        _check(
            AUDIO_CODEC, "aac", facts.acodec or "none", facts.acodec == "aac"
        ),
        _check(
            AUDIO_PROFILE,
            "LC",
            facts.aprofile or "none",
            facts.aprofile == "LC",
        ),
        _check(
            AUDIO_CHANNELS, "2 (stereo)", facts.channels, facts.channels == 2
        ),
        _check(
            SAMPLE_RATE,
            rates,
            facts.sample_rate,
            facts.sample_rate in profile.sample_rates,
        ),
    ]


def _extra_checks(
    facts: StreamFacts,
    profile: CompatProfile,
    size_cap_bytes: int | None,
    source_aspect: float | None,
) -> list[CheckResult]:
    """Check faststart, size, aspect ratio and duration."""
    results = [
        _check(
            FASTSTART,
            "moov before mdat",
            {True: "yes", False: "no", None: "unknown"}[facts.faststart],
            facts.faststart is True,
        )
    ]
    if size_cap_bytes is not None:
        results.append(
            _check(
                FILE_SIZE,
                f"<= {size_cap_bytes} bytes",
                f"{facts.size_bytes} bytes",
                facts.size_bytes <= size_cap_bytes,
            )
        )
    if source_aspect:
        ratio = facts.aspect / source_aspect
        results.append(
            _check(
                ASPECT_PRESERVED,
                "same as the source",
                f"{facts.aspect:.3f} vs {source_aspect:.3f}",
                abs(ratio - 1) <= _ASPECT_TOLERANCE,
            )
        )
    if profile.advisory_aspect:
        results.append(
            _check(
                ASPECT_RATIO,
                "9:16 (ideal for Status)",
                f"{facts.aspect:.3f}",
                abs(facts.aspect - profile.advisory_aspect) <= 0.02,
                Severity.WARNING,
            )
        )
    limit = profile.advisory_max_duration_s
    if limit:
        results.append(
            _check(
                DURATION,
                f"<= {limit:g} s",
                f"{facts.duration_s:.1f} s",
                facts.duration_s <= limit,
                Severity.WARNING,
            )
        )
    return results


def check_compliance(
    facts: StreamFacts,
    profile: CompatProfile,
    size_cap_bytes: int | None = None,
    short_cap: int | None = None,
    source_aspect: float | None = None,
) -> ComplianceReport:
    """Compare real file facts with the profile.

    Args:
        facts: What ffprobe reported for the file.
        profile: The settings the file should match.
        size_cap_bytes: Maximum file size, or None for no limit.
        short_cap: Lower limit for the short edge (never above the
            profile maximum).
        source_aspect: Aspect ratio of the original, to prove it was kept.
    """
    cap = profile.max_short_edge
    if short_cap is not None:
        cap = min(short_cap, cap)
    results = _video_checks(facts, profile, cap)
    results += _audio_checks(facts, profile)
    results += _extra_checks(facts, profile, size_cap_bytes, source_aspect)
    return ComplianceReport(tuple(results))
