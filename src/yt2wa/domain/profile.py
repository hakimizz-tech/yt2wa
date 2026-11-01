"""The WhatsApp compatibility profile.

Profiles are data. The built-in defaults can be overridden by a TOML file
(see ``config/presets.default.toml``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from typing import Any

from yt2wa.domain.errors import ConfigError
from yt2wa.domain.models import Target

_MIN_BITRATES = {144: 60, 240: 120, 360: 250, 480: 400, 720: 800, 1080: 1500}
_MAX_BITRATES = {
    144: 200,
    240: 400,
    360: 800,
    480: 1400,
    720: 2800,
    1080: 5500,
}


@dataclass(frozen=True, kw_only=True)
class CompatProfile:
    """The settings a file must match to be shared on WhatsApp."""

    name: str
    max_long_edge: int = 1920
    max_short_edge: int = 1080
    max_fps: float = 30.0
    max_h264_level: int = 40
    allowed_h264_profiles: tuple[str, ...] = (
        "Baseline",
        "Constrained Baseline",
        "Main",
        "High",
    )
    audio_bitrate_k: int = 128
    sample_rates: tuple[int, ...] = (44100, 48000)
    default_sample_rate: int = 48000
    crf: int = 23
    preset: str = "medium"
    size_cap_mb: int = 16
    floor_resolution: int = 360
    advisory_aspect: float | None = None
    advisory_max_duration_s: float | None = None
    min_video_bitrate_k: Mapping[int, int] = field(
        default_factory=lambda: dict(_MIN_BITRATES)
    )
    max_video_bitrate_k: Mapping[int, int] = field(
        default_factory=lambda: dict(_MAX_BITRATES)
    )


DEFAULT_CHAT = CompatProfile(name="chat")

# 9:16 is ideal for Status. The duration is advice only. Verify it.
DEFAULT_STATUS = replace(
    DEFAULT_CHAT,
    name="status",
    advisory_aspect=9 / 16,
    advisory_max_duration_s=60.0,
)

DEFAULT_PROFILES: Mapping[str, CompatProfile] = {
    "chat": DEFAULT_CHAT,
    "status": DEFAULT_STATUS,
}


def profile_for(
    target: Target, profiles: Mapping[str, CompatProfile]
) -> CompatProfile:
    """Return the profile used for a target.

    The original target has no profile of its own. It borrows the chat one
    so its informational report still has something to compare against.
    """
    return profiles["status" if target is Target.STATUS else "chat"]


def profile_from_mapping(
    name: str,
    data: Mapping[str, Any],
    base: CompatProfile = DEFAULT_CHAT,
) -> CompatProfile:
    """Build a profile from parsed TOML, starting from a base profile."""
    allowed = {f.name for f in fields(CompatProfile)} - {"name"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            f"Unknown setting(s) in profile '{name}': {', '.join(unknown)}.",
            hint="Compare with config/presets.default.toml.",
        )
    values = dict(data)
    try:
        for key in ("min_video_bitrate_k", "max_video_bitrate_k"):
            if key in values:
                values[key] = {int(k): int(v) for k, v in values[key].items()}
        for key in ("allowed_h264_profiles", "sample_rates"):
            if key in values:
                values[key] = tuple(values[key])
    except (AttributeError, TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid value in profile '{name}'.") from exc
    return replace(base, name=name, **values)
