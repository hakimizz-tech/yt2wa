"""Show progress on the terminal (stderr)."""

from __future__ import annotations

import sys
from typing import TextIO

from yt2wa.domain.models import Progress


class ConsoleProgress:
    """A progress callback that draws a simple line on stderr."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stderr
        self._tty = self._stream.isatty()
        self._stage: str | None = None
        self._dirty = False

    def __call__(self, progress: Progress) -> None:
        """Handle one progress update."""
        if progress.stage != self._stage:
            self.finish()
            if not self._tty:
                self._stream.write(f"  {progress.stage}...\n")
            self._stage = progress.stage
        if self._tty and progress.fraction is not None:
            percent = progress.fraction * 100
            self._stream.write(f"\r  {progress.stage:<9} {percent:5.1f}%")
            self._stream.flush()
            self._dirty = True

    def finish(self) -> None:
        """End the current line, if we were drawing on it."""
        if self._dirty:
            self._stream.write("\n")
            self._stream.flush()
            self._dirty = False
