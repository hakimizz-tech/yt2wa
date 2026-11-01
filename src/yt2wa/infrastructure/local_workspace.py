"""Scratch folders and safe publishing on the local disk."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path


class LocalWorkspace:
    """Creates job folders and publishes finished files."""

    def __init__(self, work_dir: Path | None = None) -> None:
        self._base = work_dir or Path(tempfile.gettempdir()) / "yt2wa"

    def new_job_dir(self) -> Path:
        """Create a private folder for one run."""
        self._base.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="job-", dir=self._base))

    def publish(self, src: Path, dest_dir: Path, final_name: str) -> Path:
        """Move a file into place. Readers never see a partial file."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = self._unique(dest_dir / final_name)
        try:
            os.replace(src, target)
        except OSError:
            # Different drives cannot be renamed. Copy, then rename.
            partial = target.with_name(f".{target.name}.part")
            shutil.copyfile(src, partial)
            os.replace(partial, target)
            src.unlink(missing_ok=True)
        return target

    def cleanup(self, job_dir: Path) -> None:
        """Delete a job folder and everything in it."""
        shutil.rmtree(job_dir, ignore_errors=True)

    def stale_jobs(self, max_age_s: float) -> list[Path]:
        """List job folders older than max_age_s seconds."""
        if not self._base.is_dir():
            return []
        cutoff = time.time() - max_age_s
        return [
            path
            for path in self._base.glob("job-*")
            if path.is_dir() and path.stat().st_mtime < cutoff
        ]

    @staticmethod
    def _unique(path: Path) -> Path:
        """Return a path that does not exist yet (adds -1, -2, ...)."""
        if not path.exists():
            return path
        number = 1
        while True:
            candidate = path.with_name(f"{path.stem}-{number}{path.suffix}")
            if not candidate.exists():
                return candidate
            number += 1
