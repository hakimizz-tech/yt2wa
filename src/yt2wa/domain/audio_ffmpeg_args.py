"""Build ffmpeg command lines for audio files. Pure."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from yt2wa.domain.audio_profile import AudioProfile
from yt2wa.domain.models import AudioFormat, Method, StreamFacts


@dataclass(frozen=True)
class AudioPlan:
    """Everything needed to build one audio ffmpeg command."""

    source: Path
    output: Path
    method: Method
    facts: StreamFacts
    profile: AudioProfile
    audio_format: AudioFormat
    bitrate_k: int
    tags: Mapping[str, str] = field(default_factory=dict)
    threads: int = 0
    ffmpeg_bin: str = "ffmpeg"


def build_audio_ffmpeg_args(plan: AudioPlan) -> list[str]:
    """Return the full ffmpeg argument list for an audio plan."""
    args = [
        plan.ffmpeg_bin, "-hide_banner", "-nostdin", "-y",
        "-loglevel", "error", "-progress", "pipe:1", "-nostats",
        "-i", str(plan.source),
        "-vn", "-map", "0:a:0", "-map_metadata", "-1",
    ]  # fmt: skip
    for key, value in plan.tags.items():
        args += ["-metadata", f"{key}={value}"]

    is_m4a = plan.audio_format is AudioFormat.M4A
    if plan.method is Method.REMUX:
        args += ["-c:a", "copy"]
    else:
        rate = 44100 if plan.facts.sample_rate == 44100 else (
            plan.profile.default_sample_rate
        )
        channels = 2 if (plan.facts.channels or 2) >= 2 else 1
        if is_m4a:
            args += ["-c:a", "aac", "-profile:a", "aac_low"]
        else:
            args += ["-c:a", "libmp3lame"]
        args += ["-b:a", f"{plan.bitrate_k}k", "-ar", str(rate)]
        args += ["-ac", str(channels)]
        if plan.threads > 0:
            args += ["-threads", str(plan.threads)]
    if is_m4a:
        args += ["-movflags", "+faststart"]
    else:
        args += ["-id3v2_version", "3"]
    args.append(str(plan.output))
    return args
