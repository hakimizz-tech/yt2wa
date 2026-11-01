"""Load compatibility profiles and apply environment overrides."""

from __future__ import annotations

import tomllib
from dataclasses import replace
from typing import Any

from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import ConfigError
from yt2wa.domain.profile import (
    DEFAULT_PROFILES,
    CompatProfile,
    profile_from_mapping,
)


def load_profiles(settings: Settings) -> dict[str, CompatProfile]:
    """Return the chat and status profiles."""
    profiles = dict(DEFAULT_PROFILES)
    if settings.profile_file is not None:
        try:
            with settings.profile_file.open("rb") as handle:
                data = tomllib.load(handle)
        except OSError as exc:
            raise ConfigError(
                f"Cannot read profile file {settings.profile_file}."
            ) from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Invalid TOML in profile file: {exc}") from exc
        unknown = sorted(set(data) - {"chat", "status"})
        if unknown:
            raise ConfigError(f"Unknown profile(s): {', '.join(unknown)}.")
        # Status starts from chat, so chat changes carry over.
        chat = profile_from_mapping("chat", data.get("chat", {}))
        profiles["chat"] = chat
        profiles["status"] = profile_from_mapping(
            "status",
            {**_status_defaults(), **data.get("status", {})},
            base=chat,
        )

    overrides: dict[str, Any] = {}
    if settings.max_size_mb is not None:
        overrides["size_cap_mb"] = settings.max_size_mb
    if settings.floor_resolution is not None:
        overrides["floor_resolution"] = settings.floor_resolution
    if overrides:
        profiles = {
            name: replace(profile, **overrides)
            for name, profile in profiles.items()
        }
    return profiles


def _status_defaults() -> dict[str, float]:
    """Return the advisory settings every status profile starts with."""
    status = DEFAULT_PROFILES["status"]
    return {
        "advisory_aspect": status.advisory_aspect or 0.0,
        "advisory_max_duration_s": status.advisory_max_duration_s or 0.0,
    }
