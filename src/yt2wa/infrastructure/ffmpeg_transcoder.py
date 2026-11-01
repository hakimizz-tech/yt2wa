"""Run ffmpeg and report its progress."""

from __future__ import annotations

import re
import subprocess
from collections import deque
from collections.abc import Sequence

from yt2wa.domain.errors import MissingBinaryError, TranscodeError
from yt2wa.domain.models import Progress, ProgressCallback

# Lines ffmpeg prints with "-progress". Anything else is an error message.
_PROGRESS_LINE = re.compile(
    r"^(frame|fps|stream_\d+_\d+_q|bitrate|total_size|out_time_us|"
    r"out_time_ms|out_time|dup_frames|drop_frames|speed|progress)="
)


class FfmpegTranscoder:
    """Transcoder implemented with the ffmpeg program."""

    def run(
        self,
        args: Sequence[str],
        duration_s: float,
        on_progress: ProgressCallback,
    ) -> None:
        """Run ffmpeg. Raises TranscodeError if it fails."""
        try:
            proc = subprocess.Popen(
                list(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise MissingBinaryError(f"'{args[0]}' was not found.") from exc

        errors: deque[str] = deque(maxlen=15)
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                if not _PROGRESS_LINE.match(line):
                    errors.append(line)
                elif line.startswith("out_time_us=") and duration_s > 0:
                    self._report(line, duration_s, on_progress)
            code = proc.wait()
        finally:
            # Also runs on Ctrl+C, so ffmpeg never keeps running behind us.
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if code != 0:
            raise TranscodeError(
                f"ffmpeg failed with exit code {code}.",
                hint="\n".join(errors) or None,
            )
        on_progress(Progress("convert", 1.0))

    @staticmethod
    def _report(
        line: str, duration_s: float, on_progress: ProgressCallback
    ) -> None:
        """Turn an out_time_us line into a progress update."""
        try:
            seconds = int(line.split("=", 1)[1]) / 1_000_000
        except ValueError:
            return
        fraction = max(0.0, min(1.0, seconds / duration_s))
        on_progress(Progress("convert", fraction))
