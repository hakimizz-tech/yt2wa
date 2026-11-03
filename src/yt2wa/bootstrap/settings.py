"""Settings read from environment variables (12-factor config)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from yt2wa.domain.errors import ConfigError
from yt2wa.domain.formats import parse_resolution
from yt2wa.domain.models import AudioFormat, SearchProviderName, Target

PREFIX = "YT2WA_"


def load_dotenv(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines from a .env file (development only)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    """Read an integer setting."""
    raw = env.get(PREFIX + key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{PREFIX}{key} must be a number.") from exc


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    """Read a decimal setting."""
    raw = env.get(PREFIX + key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{PREFIX}{key} must be a number.") from exc


def _path(env: Mapping[str, str], key: str) -> Path | None:
    """Read an optional path setting."""
    raw = env.get(PREFIX + key)
    return Path(raw).expanduser() if raw else None


@dataclass(frozen=True)
class Settings:
    """Every configurable value, with its default."""

    default_target: Target = Target.CHAT
    default_resolution: int = 480
    max_size_mb: int | None = None
    floor_resolution: int | None = None
    profile_file: Path | None = None
    work_dir: Path | None = None
    output_dir: Path = Path("out")
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    ffmpeg_threads: int = 0
    net_retries: int = 3
    cookies_file: Path | None = None
    log_level: str = "INFO"
    log_format: str = "text"
    search_limit: int = 5
    search_provider: SearchProviderName | None = None  # None means auto.
    min_confidence: float = 0.6
    audio_format: AudioFormat = AudioFormat.M4A
    audio_bitrate_k: int | None = None
    audio_profile_file: Path | None = None

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        dotenv: Path | None = None,
    ) -> Settings:
        """Build settings. Real environment variables beat .env."""
        env: dict[str, str] = {}
        env.update(load_dotenv(dotenv or Path(".env")))
        env.update(environ if environ is not None else os.environ)

        try:
            target = Target(env.get(PREFIX + "DEFAULT_TARGET", "chat"))
        except ValueError as exc:
            raise ConfigError(
                f"{PREFIX}DEFAULT_TARGET must be original, chat or status."
            ) from exc
        resolution = parse_resolution(
            env.get(PREFIX + "DEFAULT_RESOLUTION", "480")
        )
        log_format = env.get(PREFIX + "LOG_FORMAT", "text")
        if log_format not in ("text", "json"):
            raise ConfigError(f"{PREFIX}LOG_FORMAT must be text or json.")

        provider_name = env.get(PREFIX + "SEARCH_PROVIDER", "auto")
        try:
            provider = (
                None
                if provider_name == "auto"
                else SearchProviderName(provider_name)
            )
            audio_format = AudioFormat(env.get(PREFIX + "AUDIO_FORMAT", "m4a"))
        except ValueError as exc:
            raise ConfigError(
                f"Invalid {PREFIX}SEARCH_PROVIDER or {PREFIX}AUDIO_FORMAT.",
                hint="Providers: auto, ytsearch, ytmusic-url, ytmusicapi. "
                "Audio formats: m4a, mp3.",
            ) from exc
        search_limit = _int(env, "SEARCH_LIMIT", 5)
        if not 1 <= search_limit <= 25:
            raise ConfigError(f"{PREFIX}SEARCH_LIMIT must be 1 to 25.")
        min_confidence = _float(env, "MIN_CONFIDENCE", 0.6)
        if not 0.0 <= min_confidence <= 1.0:
            raise ConfigError(f"{PREFIX}MIN_CONFIDENCE must be 0 to 1.")
        audio_bitrate = env.get(PREFIX + "AUDIO_BITRATE_K")

        size = env.get(PREFIX + "MAX_SIZE_MB")
        floor = env.get(PREFIX + "MIN_RESOLUTION_FLOOR")
        return cls(
            default_target=target,
            default_resolution=resolution,
            max_size_mb=_int(env, "MAX_SIZE_MB", 0) if size else None,
            floor_resolution=(
                _int(env, "MIN_RESOLUTION_FLOOR", 0) if floor else None
            ),
            profile_file=_path(env, "PROFILE_FILE"),
            work_dir=_path(env, "WORK_DIR"),
            output_dir=_path(env, "OUTPUT_DIR") or Path("out"),
            ffmpeg_bin=env.get(PREFIX + "FFMPEG_BIN", "ffmpeg"),
            ffprobe_bin=env.get(PREFIX + "FFPROBE_BIN", "ffprobe"),
            ffmpeg_threads=_int(env, "FFMPEG_THREADS", 0),
            net_retries=_int(env, "NET_RETRIES", 3),
            cookies_file=_path(env, "COOKIES_FILE"),
            log_level=env.get(PREFIX + "LOG_LEVEL", "INFO").upper(),
            log_format=log_format,
            search_limit=search_limit,
            search_provider=provider,
            min_confidence=min_confidence,
            audio_format=audio_format,
            audio_bitrate_k=(
                _int(env, "AUDIO_BITRATE_K", 128) if audio_bitrate else None
            ),
            audio_profile_file=_path(env, "AUDIO_PROFILE_FILE"),
        )
