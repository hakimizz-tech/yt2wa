"""Small helpers for running external programs safely."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence

from yt2wa.domain.errors import MissingBinaryError


def resolve_binary(name: str) -> str:
    """Return the full path of a program, or raise if it is missing."""
    found = shutil.which(name)
    if found is None:
        raise MissingBinaryError(
            f"'{name}' was not found.",
            hint=(
                "Install ffmpeg (https://ffmpeg.org) or set "
                "YT2WA_FFMPEG_BIN / YT2WA_FFPROBE_BIN."
            ),
        )
    return found


def run_capture(
    args: Sequence[str], timeout: float | None = 60
) -> subprocess.CompletedProcess[str]:
    """Run a program and capture its text output.

    The command is always an argument list, never a shell string.
    """
    try:
        return subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MissingBinaryError(f"'{args[0]}' was not found.") from exc
