"""Rules for choosing and building searches. Pure."""

from __future__ import annotations

from urllib.parse import quote_plus

from yt2wa.domain.models import SearchKind, SearchProviderName
from yt2wa.domain.text_rules import clean_query

MAX_LIMIT = 25

_MUSIC_SEARCH = "https://music.youtube.com/search?q="

# Best method first. The others are backups if it fails or finds nothing.
_MUSIC_CHAIN = (
    SearchProviderName.YTMUSICAPI,
    SearchProviderName.YTMUSIC_URL,
    SearchProviderName.YTSEARCH,
)
_DEFAULT_CHAIN = (SearchProviderName.YTSEARCH,)


def build_music_search_url(query: str) -> str:
    """Return the YouTube Music search page URL for a query."""
    return _MUSIC_SEARCH + quote_plus(clean_query(query))


def select_provider_chain(
    kind: SearchKind, requested: SearchProviderName | None
) -> tuple[SearchProviderName, ...]:
    """Return the search methods to try, in order.

    An explicitly requested method is used alone, with no fallback.
    """
    if requested is not None:
        return (requested,)
    return _MUSIC_CHAIN if kind is SearchKind.MUSIC else _DEFAULT_CHAIN
