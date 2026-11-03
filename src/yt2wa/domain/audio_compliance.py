"""Check an audio file against the audio profile. Pure.

Mirrors ``compliance.py``: one function decides whether a download can be
copied, verifies the result and powers ``verify`` for audio files.
"""

from __future__ import annotations

from yt2wa.domain import compliance as c
from yt2wa.domain.audio_profile import AudioProfile
from yt2wa.domain.models import (
    AudioFormat,
    CheckResult,
    ComplianceReport,
    Method,
    PathDecision,
    StreamFacts,
)

AUDIO_CONTAINER = "audio_container"
AUDIO_BITRATE = "audio_bitrate"
NO_VIDEO = "no_video_stream"

_REENCODE = frozenset(
    {
        c.AUDIO_PRESENT,
        c.AUDIO_CODEC,
        c.AUDIO_PROFILE,
        c.AUDIO_CHANNELS,
        c.SAMPLE_RATE,
        AUDIO_BITRATE,
    }
)
_REMUX = frozenset({AUDIO_CONTAINER, NO_VIDEO, c.FASTSTART})


def _check(
    name: str, expected: object, actual: object, passed: bool
) -> CheckResult:
    """Build an error-level check result."""
    return CheckResult(name, str(expected), str(actual), passed)


def check_audio_compliance(
    facts: StreamFacts,
    profile: AudioProfile,
    size_cap_bytes: int | None = None,
    audio_format: AudioFormat = AudioFormat.M4A,
    max_bitrate_k: int | None = None,
) -> ComplianceReport:
    """Compare real audio file facts with the audio profile."""
    is_m4a = audio_format is AudioFormat.M4A
    tokens = {part.strip() for part in facts.container.split(",")}
    container_ok = bool(tokens & {"mp4", "m4a"}) if is_m4a else "mp3" in tokens
    results = [
        _check(
            c.AUDIO_PRESENT,
            "an audio stream",
            "yes" if facts.has_audio else "none",
            facts.has_audio,
        ),
        _check(
            AUDIO_CONTAINER,
            "mp4/m4a" if is_m4a else "mp3",
            facts.container,
            container_ok,
        ),
        _check(NO_VIDEO, "none", facts.vcodec or "none", facts.vcodec is None),
    ]
    if facts.has_audio:
        wanted = "aac" if is_m4a else "mp3"
        limit = (max_bitrate_k or profile.default_bitrate_k) * (
            profile.bitrate_tolerance
        )
        rates = " or ".join(str(rate) for rate in profile.sample_rates)
        results += [
            _check(c.AUDIO_CODEC, wanted, facts.acodec, facts.acodec == wanted)
        ]
        if is_m4a:
            results.append(
                _check(
                    c.AUDIO_PROFILE,
                    "LC",
                    facts.aprofile or "none",
                    facts.aprofile == "LC",
                )
            )
        results += [
            _check(
                c.AUDIO_CHANNELS,
                f"<= {profile.max_channels}",
                facts.channels,
                facts.channels is not None
                and 1 <= facts.channels <= profile.max_channels,
            ),
            _check(
                c.SAMPLE_RATE,
                rates,
                facts.sample_rate,
                facts.sample_rate in profile.sample_rates,
            ),
            _check(
                AUDIO_BITRATE,
                f"<= {limit:.0f} kbit/s",
                "unknown" if facts.abitrate_k is None else facts.abitrate_k,
                facts.abitrate_k is None or facts.abitrate_k <= limit,
            ),
        ]
    if is_m4a:
        results.append(
            _check(
                c.FASTSTART,
                "moov before mdat",
                {True: "yes", False: "no", None: "unknown"}[facts.faststart],
                facts.faststart is True,
            )
        )
    if size_cap_bytes is not None:
        results.append(
            _check(
                c.FILE_SIZE,
                f"<= {size_cap_bytes} bytes",
                f"{facts.size_bytes} bytes",
                facts.size_bytes <= size_cap_bytes,
            )
        )
    return ComplianceReport(tuple(results))


def decide_audio_path(report: ComplianceReport) -> PathDecision:
    """Choose between copying the audio stream and re-encoding it."""
    failed = [result.name for result in report.errors]
    reencode = [name for name in failed if name in _REENCODE]
    if reencode:
        return PathDecision(Method.TRANSCODE, tuple(reencode))
    if c.FILE_SIZE in failed:
        return PathDecision(Method.TRANSCODE, ("file is over the size cap",))
    if failed:
        return PathDecision(Method.REMUX, tuple(failed))
    return PathDecision(Method.REMUX, ("already compliant",))
