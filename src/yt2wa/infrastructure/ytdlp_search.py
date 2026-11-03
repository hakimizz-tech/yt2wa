"""Search YouTube with yt-dlp. Two methods share this adapter.

``ytsearch`` uses the ``ytsearchN:`` prefix. ``ytmusic-url`` loads the
YouTube Music search page URL. Both use flat extraction, so a search
costs one request.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from yt2wa.domain.models import (
    SearchCandidate,
    SearchKind,
    SearchProviderName,
)
from yt2wa.domain.ranking import infer_origin
from yt2wa.domain.search_providers import build_music_search_url
from yt2wa.domain.text_rules import clean_query
from yt2wa.infrastructure.ytdlp_downloader import (
    YtDlpLogger,
    _load_yt_dlp,
    classify_download_error,
)

_VIDEO_ID = re.compile(r"^[\w-]{11}$")

# (target, options) -> yt-dlp info dict. Replaceable in tests.
Extractor = Callable[[str, dict[str, Any]], dict[str, Any]]


def candidate_from_flat_entry(
    entry: dict[str, Any], position: int, provider: SearchProviderName
) -> SearchCandidate | None:
    """Turn one flat yt-dlp entry into a candidate, or None to skip."""
    video_id = str(entry.get("id") or "")
    if not _VIDEO_ID.match(video_id):
        return None  # Playlists and channels have longer ids.
    if entry.get("ie_key") not in (None, "Youtube"):
        return None
    title = str(entry.get("title") or "")
    channel = str(entry.get("channel") or entry.get("uploader") or "")
    views = entry.get("view_count")
    return SearchCandidate(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        channel=channel,
        duration_s=float(entry.get("duration") or 0),
        view_count=int(views) if isinstance(views, (int, float)) else None,
        position=position,
        origin=infer_origin(title, channel),
        provider=provider,
    )


def _default_extractor(
    target: str, options: dict[str, Any]
) -> dict[str, Any]:
    """Run yt-dlp and translate its errors."""
    yt_dlp = _load_yt_dlp()
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info: dict[str, Any] = ydl.extract_info(target, download=False)
    except (yt_dlp.utils.YoutubeDLError, OSError) as exc:
        raise classify_download_error(str(exc)) from exc
    return info


class YtDlpSearchProvider:
    """SearchProvider implemented with yt-dlp."""

    def __init__(
        self,
        mode: SearchProviderName,
        retries: int = 3,
        cookies_file: Path | None = None,
        extractor: Extractor | None = None,
    ) -> None:
        if mode not in (
            SearchProviderName.YTSEARCH,
            SearchProviderName.YTMUSIC_URL,
        ):
            raise ValueError(f"unsupported yt-dlp search mode: {mode}")
        self._mode = mode
        self._retries = retries
        self._cookies_file = cookies_file
        self._extract = extractor or _default_extractor

    def search(
        self, query: str, kind: SearchKind, limit: int
    ) -> list[SearchCandidate]:
        """Search and return candidates in listed order."""
        text = clean_query(query)
        if self._mode is SearchProviderName.YTSEARCH:
            target = f"ytsearch{limit}:{text}"
        else:
            target = build_music_search_url(text)

        info = self._extract(target, self._options(limit))
        candidates: list[SearchCandidate] = []
        seen: set[str] = set()
        for entry in info.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            candidate = candidate_from_flat_entry(
                entry, len(candidates), self._mode
            )
            if candidate is None or candidate.video_id in seen:
                continue
            seen.add(candidate.video_id)
            candidates.append(candidate)
        return candidates[:limit]

    def _options(self, limit: int) -> dict[str, Any]:
        """Return the yt-dlp options for a search."""
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "logger": YtDlpLogger(),
            "skip_download": True,
            "extract_flat": True,
            "playlistend": limit,
            "retries": self._retries,
            "socket_timeout": 30,
        }
        if self._cookies_file is not None:
            options["cookiefile"] = str(self._cookies_file)
        return options
