"""Decide what kind of YouTube link we were given."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from yt2wa.domain.models import SourceKind, SourceRef

_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_VIDEO_ID = re.compile(r"^[\w-]{11}$")
_VIDEO_PREFIXES = {"live", "embed", "v"}


def _ref(url: str, kind: SourceKind, video_id: str | None) -> SourceRef:
    """Build a reference, rejecting ids that do not look right."""
    if video_id is None or not _VIDEO_ID.match(video_id):
        return SourceRef(url, SourceKind.UNSUPPORTED)
    return SourceRef(url, kind, video_id)


def classify_url(url: str) -> SourceRef:
    """Classify a link as a video, a Short or unsupported."""
    url = url.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in _HOSTS:
        return SourceRef(url, SourceKind.UNSUPPORTED)

    parts = [p for p in parsed.path.split("/") if p]
    if host.endswith("youtu.be"):
        return _ref(url, SourceKind.VIDEO, parts[0] if parts else None)
    if not parts:
        return SourceRef(url, SourceKind.UNSUPPORTED)

    head = parts[0]
    if head == "watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        return _ref(url, SourceKind.VIDEO, video_id)
    if head == "shorts" and len(parts) > 1:
        return _ref(url, SourceKind.SHORT, parts[1])
    if head in _VIDEO_PREFIXES and len(parts) > 1:
        return _ref(url, SourceKind.VIDEO, parts[1])
    return SourceRef(url, SourceKind.UNSUPPORTED)


def sanitize_filename(title: str, max_len: int = 80) -> str:
    """Turn a video title into a safe file name (without extension)."""
    cleaned = re.sub(r"[^\w\s.-]", "", title, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned.strip("._-")[:max_len].rstrip("._-")
    reserved = {"con", "prn", "aux", "nul"}
    if not cleaned or cleaned.lower() in reserved:
        return "video"
    return cleaned
