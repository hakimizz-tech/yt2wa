"""Build ffmpeg command lines. Pure: nothing is executed here."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yt2wa.domain.models import LadderStep, Method, StreamFacts
from yt2wa.domain.profile import CompatProfile
from yt2wa.domain.size_guard import rung_for


@dataclass(frozen=True)
class FfmpegPlan:
    """Everything needed to build one ffmpeg command."""

    source: Path
    output: Path
    method: Method
    facts: StreamFacts
    profile: CompatProfile
    short_cap: int
    step: LadderStep | None = None
    threads: int = 0
    ffmpeg_bin: str = "ffmpeg"


def select_h264_level(width: int, height: int, fps: float = 30.0) -> str:
    """Pick an H.264 level that fits the picture size at up to 30 fps."""
    pixels = width * height
    if pixels <= 414_720:  # 854x480 and smaller.
        return "3.0"
    if pixels <= 921_600:  # 1280x720 and smaller.
        return "3.1"
    return "4.0"


def _even(value: float) -> int:
    """Round to the nearest even number, at least 2."""
    return max(2, round(value / 2) * 2)


def target_size(
    facts: StreamFacts, short_cap: int, long_cap: int
) -> tuple[int, int]:
    """Return the output size. Only ever scales down, keeps the aspect."""
    width, height = facts.display_size
    scale = min(
        1.0,
        short_cap / min(width, height),
        long_cap / max(width, height),
    )
    return _even(width * scale), _even(height * scale)


def build_video_filter(
    facts: StreamFacts, size: tuple[int, int], max_fps: float
) -> str | None:
    """Return the ``-vf`` value, or None when no filter is needed."""
    parts = []
    if size != facts.display_size:
        parts.append(f"scale={size[0]}:{size[1]}:flags=lanczos")
    if facts.fps > max_fps + 0.05:
        parts.append(f"fps={max_fps:g}")
    return ",".join(parts) or None


def _video_args(plan: FfmpegPlan) -> list[str]:
    """Return the video encoder arguments."""
    profile = plan.profile
    size = target_size(plan.facts, plan.short_cap, profile.max_long_edge)
    fps_out = min(plan.facts.fps, profile.max_fps)
    args: list[str] = []
    video_filter = build_video_filter(plan.facts, size, profile.max_fps)
    if video_filter:
        args += ["-vf", video_filter]
    args += [
        "-c:v", "libx264",
        "-preset", profile.preset,
        "-profile:v", "high",
        "-level:v", select_h264_level(size[0], size[1], fps_out),
        "-pix_fmt", "yuv420p",
    ]  # fmt: skip
    step = plan.step
    if step is not None and step.kind == "bitrate" and step.video_bitrate_k:
        rate = step.video_bitrate_k
        args += ["-b:v", f"{rate}k", "-maxrate", f"{rate}k"]
        args += ["-bufsize", f"{rate * 2}k"]
    else:
        rung = rung_for(min(size))
        peak = profile.max_video_bitrate_k.get(rung, 5500)
        args += ["-crf", str(profile.crf), "-maxrate", f"{peak}k"]
        args += ["-bufsize", f"{peak * 2}k"]
    return args


def _audio_args(plan: FfmpegPlan) -> list[str]:
    """Return the audio encoder arguments."""
    if not plan.facts.has_audio:
        return ["-an"]
    profile = plan.profile
    rate = 44100 if plan.facts.sample_rate == 44100 else (
        profile.default_sample_rate
    )
    return [
        "-c:a", "aac",
        "-profile:a", "aac_low",
        "-b:a", f"{profile.audio_bitrate_k}k",
        "-ar", str(rate),
        "-ac", "2",
    ]  # fmt: skip


def build_ffmpeg_args(plan: FfmpegPlan) -> list[str]:
    """Return the full ffmpeg argument list for a plan."""
    args = [
        plan.ffmpeg_bin, "-hide_banner", "-nostdin", "-y",
        "-loglevel", "error", "-progress", "pipe:1", "-nostats",
        "-i", str(plan.source),
        "-map", "0:v:0", "-map", "0:a:0?",
    ]  # fmt: skip
    if plan.method is Method.REMUX:
        args += ["-c", "copy"]
    else:
        args += _video_args(plan) + _audio_args(plan)
        if plan.threads > 0:
            args += ["-threads", str(plan.threads)]
    args += ["-movflags", "+faststart", str(plan.output)]
    return args
