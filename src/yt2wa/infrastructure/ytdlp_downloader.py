"""Download videos with the yt-dlp library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yt2wa.domain.errors import (
    AgeRestrictedError,
    DomainError,
    GeoBlockedError,
    MissingBinaryError,
    NetworkError,
    PrivateVideoError,
    RemovedVideoError,
    SourceUnavailableError,
)
from yt2wa.domain.models import (
    FormatChoice,
    Progress,
    ProgressCallback,
    SourceMetadata,
    SourceRef,
)

_COOKIE_HINT = "Provide a cookies file with YT2WA_COOKIES_FILE."


def classify_download_error(message: str) -> DomainError:
    """Turn a yt-dlp error message into one of our own errors."""
    text = message.lower()
    first_line = message.strip().splitlines()[0] if message.strip() else ""
    if "private video" in text:
        return PrivateVideoError("This video is private.")
    if "confirm your age" in text or "age-restricted" in text:
        return AgeRestrictedError(
            "This video is age restricted.", hint=_COOKIE_HINT
        )
    if "country" in text and ("not available" in text or "blocked" in text):
        return GeoBlockedError("This video is blocked in your country.")
    if any(
        phrase in text
        for phrase in (
            "video unavailable",
            "has been removed",
            "no longer available",
            "has been terminated",
        )
    ):
        return RemovedVideoError("This video is unavailable or was removed.")
    if "sign in to confirm" in text:
        return SourceUnavailableError(
            "YouTube asked for a sign-in check.", hint=_COOKIE_HINT
        )
    if any(
        phrase in text
        for phrase in (
            "http error 429",
            "timed out",
            "temporary failure",
            "name or service not known",
            "getaddrinfo",
            "connection",
            "urlopen error",
            "unable to download",
        )
    ):
        return NetworkError(
            "The download failed because of a network problem.",
            hint="Check your connection and try again.",
        )
    return SourceUnavailableError(first_line or "The video is unavailable.")


def _load_yt_dlp() -> Any:
    """Import yt-dlp when it is first needed."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise MissingBinaryError(
            "yt-dlp is not installed.", hint="Run: pip install yt-dlp"
        ) from exc
    return yt_dlp


class YtDlpDownloader:
    """Downloader implemented with the yt-dlp Python API."""

    def __init__(
        self, retries: int = 3, cookies_file: Path | None = None
    ) -> None:
        self._retries = retries
        self._cookies_file = cookies_file

    def probe(self, ref: SourceRef) -> SourceMetadata:
        """Fetch metadata without downloading the video."""
        yt_dlp = _load_yt_dlp()
        options = self._base_options() | {"skip_download": True}
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(ref.url, download=False)
        except (yt_dlp.utils.YoutubeDLError, OSError) as exc:
            raise classify_download_error(str(exc)) from exc
        return SourceMetadata(
            video_id=str(info.get("id", ref.video_id or "")),
            title=str(info.get("title") or info.get("id") or "video"),
            duration_s=float(info.get("duration") or 0),
            uploader=info.get("uploader"),
        )

    def download(
        self,
        ref: SourceRef,
        choice: FormatChoice,
        dest_dir: Path,
        on_progress: ProgressCallback,
    ) -> Path:
        """Download the chosen streams and return the file path."""
        yt_dlp = _load_yt_dlp()
        dest_dir.mkdir(parents=True, exist_ok=True)

        def hook(data: dict[str, Any]) -> None:
            if data.get("status") != "downloading":
                return
            total = data.get("total_bytes") or data.get(
                "total_bytes_estimate"
            )
            done = data.get("downloaded_bytes") or 0
            if total:
                on_progress(Progress("download", min(1.0, done / total)))

        options = self._base_options() | {
            "format": choice.selector,
            "format_sort": list(choice.sort),
            "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
            "progress_hooks": [hook],
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(ref.url, download=True)
                downloads = info.get("requested_downloads") or []
                if downloads and downloads[0].get("filepath"):
                    path = Path(downloads[0]["filepath"])
                else:
                    path = Path(ydl.prepare_filename(info))
        except (yt_dlp.utils.YoutubeDLError, OSError) as exc:
            raise classify_download_error(str(exc)) from exc
        if not path.exists():
            raise SourceUnavailableError("The download finished but no file.")
        on_progress(Progress("download", 1.0))
        return path

    def _base_options(self) -> dict[str, Any]:
        """Return the yt-dlp options shared by every call."""
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "retries": self._retries,
            "fragment_retries": self._retries,
            "socket_timeout": 30,
        }
        if self._cookies_file is not None:
            options["cookiefile"] = str(self._cookies_file)
        return options
