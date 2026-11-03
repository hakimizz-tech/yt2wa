"""The audio compatibility profile (data, like the video profile)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from typing import Any

from yt2wa.domain.errors import ConfigError


@dataclass(frozen=True, kw_only=True)
class AudioProfile:
    """The settings an audio file must match to be shared on WhatsApp."""

    name: str = "audio"
    sample_rates: tuple[int, ...] = (44100, 48000)
    default_sample_rate: int = 48000
    max_channels: int = 2
    default_bitrate_k: int = 128
    ladder_bitrates_k: tuple[int, ...] = (128, 96, 64)
    min_bitrate_k: int = 48
    bitrate_tolerance: float = 1.15
    size_cap_mb: int = 16


DEFAULT_AUDIO = AudioProfile()


def audio_profile_from_mapping(
    data: Mapping[str, Any], base: AudioProfile = DEFAULT_AUDIO
) -> AudioProfile:
    """Build an audio profile from parsed TOML."""
    allowed = {f.name for f in fields(AudioProfile)}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            f"Unknown setting(s) in audio profile: {', '.join(unknown)}.",
            hint="Compare with config/audio.default.toml.",
        )
    values = dict(data)
    try:
        for key in ("sample_rates", "ladder_bitrates_k"):
            if key in values:
                values[key] = tuple(int(v) for v in values[key])
    except (TypeError, ValueError) as exc:
        raise ConfigError("Invalid value in the audio profile.") from exc
    return replace(base, **values)
