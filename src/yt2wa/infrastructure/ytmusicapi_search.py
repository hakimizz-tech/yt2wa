"""Search YouTube Music with the optional ytmusicapi library.

Used without logging in. Install it with: pip install "yt2wa[music]"
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from yt2wa.domain.errors import (
    MissingBinaryError,
    NetworkError,
    SourceUnavailableError,
)
from yt2wa.domain.models import (
    CandidateOrigin,
    SearchCandidate,
    SearchKind,
    SearchProviderName,
)
from yt2wa.domain.text_rules import (
    clean_query,
    parse_duration,
    parse_view_count,
)

_VIDEO_ID = re.compile(r"^[\w-]{11}$")
_FILTERS = {SearchKind.MUSIC: "songs", SearchKind.VIDEO: "videos"}


def _origin(item: dict[str, Any]) -> CandidateOrigin:
    """Map ytmusicapi result and video types to our own origin."""
    video_type = item.get("videoType")
    if item.get("resultType") == "song":
        return CandidateOrigin.MUSIC_TRACK
    if video_type == "MUSIC_VIDEO_TYPE_ATV":
        return CandidateOrigin.MUSIC_TRACK
    if video_type in (
        "MUSIC_VIDEO_TYPE_OMV",
        "MUSIC_VIDEO_TYPE_OFFICIAL_SOURCE_MUSIC",
    ):
        return CandidateOrigin.OFFICIAL_VIDEO
    if video_type == "MUSIC_VIDEO_TYPE_UGC":
        return CandidateOrigin.USER_UPLOAD
    return CandidateOrigin.UNKNOWN


def candidate_from_ytmusic_item(
    item: dict[str, Any], position: int
) -> SearchCandidate | None:
    """Turn one ytmusicapi result into a candidate, or None to skip.

    Artists, albums and playlists have no video id and are skipped.
    """
    video_id = item.get("videoId")
    if not isinstance(video_id, str) or not _VIDEO_ID.match(video_id):
        return None
    artists = tuple(
        str(a["name"])
        for a in item.get("artists") or []
        if isinstance(a, dict) and a.get("name")
    )
    album_info = item.get("album")
    album = album_info.get("name") if isinstance(album_info, dict) else None
    duration = item.get("duration_seconds") or parse_duration(
        item.get("duration")
    )
    return SearchCandidate(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=str(item.get("title") or ""),
        channel=artists[0] if artists else "",
        duration_s=float(duration or 0),
        view_count=parse_view_count(item.get("views")),
        position=position,
        origin=_origin(item),
        provider=SearchProviderName.YTMUSICAPI,
        artists=artists,
        album=str(album) if album else None,
    )


def _default_factory() -> Any:
    """Create the ytmusicapi client when it is first needed."""
    try:
        from ytmusicapi import YTMusic
    except ImportError as exc:
        raise MissingBinaryError(
            "ytmusicapi is not installed.",
            hint='Install it with: pip install "yt2wa[music]"',
        ) from exc
    return YTMusic()


class YtMusicApiSearchProvider:
    """SearchProvider implemented with ytmusicapi."""

    def __init__(
        self, client_factory: Callable[[], Any] | None = None
    ) -> None:
        self._factory = client_factory or _default_factory
        self._client: Any = None

    def search(
        self, query: str, kind: SearchKind, limit: int
    ) -> list[SearchCandidate]:
        """Search YouTube Music and return candidates in listed order."""
        if self._client is None:
            self._client = self._factory()
        try:
            items = self._client.search(
                clean_query(query), filter=_FILTERS.get(kind), limit=limit
            )
        except OSError as exc:
            raise NetworkError(
                "The YouTube Music search failed because of a network "
                "problem.",
                hint="Check your connection and try again.",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            # The library has no stable base exception, so translate all.
            raise SourceUnavailableError(
                f"ytmusicapi failed: {exc}",
                hint="Upgrade it with: pip install -U ytmusicapi",
            ) from exc

        candidates: list[SearchCandidate] = []
        seen: set[str] = set()
        for item in items or []:
            if not isinstance(item, dict):
                continue
            candidate = candidate_from_ytmusic_item(item, len(candidates))
            if candidate is None or candidate.video_id in seen:
                continue
            seen.add(candidate.video_id)
            candidates.append(candidate)
        return candidates[:limit]
