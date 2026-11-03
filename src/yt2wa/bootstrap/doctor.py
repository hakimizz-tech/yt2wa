"""Environment checks for the ``doctor`` command."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from datetime import date

from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import MissingBinaryError
from yt2wa.infrastructure.process import resolve_binary, run_capture

MIN_FFMPEG_MAJOR = 4
MAX_YTDLP_AGE_DAYS = 180


@dataclass(frozen=True)
class DoctorCheck:
    """The result of one environment check."""

    name: str
    ok: bool
    detail: str


def _check_python() -> DoctorCheck:
    """Check the Python version."""
    version = ".".join(str(part) for part in sys.version_info[:3])
    return DoctorCheck("python", sys.version_info >= (3, 11), version)


def _check_binary(label: str, name: str) -> DoctorCheck:
    """Check that ffmpeg or ffprobe exists and is recent enough."""
    try:
        path = resolve_binary(name)
        output = run_capture([path, "-version"], timeout=15).stdout
    except MissingBinaryError as exc:
        return DoctorCheck(label, False, exc.message)
    first = output.splitlines()[0] if output else "unknown version"
    match = re.search(r"version n?(\d+)", first)
    if match and int(match.group(1)) < MIN_FFMPEG_MAJOR:
        return DoctorCheck(label, False, f"{first} (need >= 4)")
    return DoctorCheck(label, True, first)


def _check_encoders(ffmpeg_bin: str) -> DoctorCheck:
    """Check that ffmpeg can encode H.264 and AAC."""
    try:
        output = run_capture(
            [resolve_binary(ffmpeg_bin), "-hide_banner", "-encoders"],
            timeout=15,
        ).stdout
    except MissingBinaryError as exc:
        return DoctorCheck("encoders", False, exc.message)
    missing = [
        name for name in ("libx264", " aac ") if name not in output
    ]
    if missing:
        return DoctorCheck(
            "encoders", False, f"missing: {', '.join(missing).strip()}"
        )
    return DoctorCheck("encoders", True, "libx264 and aac available")


def _check_ytdlp() -> DoctorCheck:
    """Check that yt-dlp is installed and not too old."""
    try:
        from yt_dlp.version import __version__
    except ImportError:
        return DoctorCheck("yt-dlp", False, "not installed")
    try:
        year, month, day = (int(p) for p in __version__.split(".")[:3])
        age = (date.today() - date(year, month, day)).days
    except ValueError:
        return DoctorCheck("yt-dlp", True, __version__)
    note = " (old, consider upgrading)" if age > MAX_YTDLP_AGE_DAYS else ""
    return DoctorCheck("yt-dlp", True, f"{__version__}, {age} days old{note}")


def _check_ytmusicapi() -> DoctorCheck:
    """Report the optional ytmusicapi package. Absent is not a failure."""
    if importlib.util.find_spec("ytmusicapi") is None:
        return DoctorCheck(
            "ytmusicapi",
            True,
            'not installed (optional: pip install "yt2wa[music]")',
        )
    return DoctorCheck("ytmusicapi", True, "installed")


def run_doctor(settings: Settings) -> list[DoctorCheck]:
    """Run every environment check."""
    return [
        _check_python(),
        _check_binary("ffmpeg", settings.ffmpeg_bin),
        _check_binary("ffprobe", settings.ffprobe_bin),
        _check_encoders(settings.ffmpeg_bin),
        _check_ytdlp(),
        _check_ytmusicapi(),
    ]
