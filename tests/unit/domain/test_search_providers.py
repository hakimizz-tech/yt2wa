import pytest

from yt2wa.domain.models import SearchKind, SearchProviderName
from yt2wa.domain.search_providers import (
    build_music_search_url,
    select_provider_chain,
)

P = SearchProviderName


@pytest.mark.parametrize(
    ("kind", "requested", "expected"),
    [
        (SearchKind.MUSIC, None, (P.YTMUSICAPI, P.YTMUSIC_URL, P.YTSEARCH)),
        (SearchKind.VIDEO, None, (P.YTSEARCH,)),
        (SearchKind.ANY, None, (P.YTSEARCH,)),
        (SearchKind.MUSIC, P.YTSEARCH, (P.YTSEARCH,)),
        (SearchKind.VIDEO, P.YTMUSICAPI, (P.YTMUSICAPI,)),
        (SearchKind.ANY, P.YTMUSIC_URL, (P.YTMUSIC_URL,)),
    ],
)
def test_select_provider_chain(kind, requested, expected):
    assert select_provider_chain(kind, requested) == expected


def test_music_url_is_encoded():
    url = build_music_search_url('daft punk & co #1 "quoted"')
    assert url.startswith("https://music.youtube.com/search?q=")
    assert " " not in url and "&co" not in url and "#" not in url
    assert "%26" in url and "%23" in url


def test_music_url_handles_non_latin_text():
    assert "%" in build_music_search_url(
        "\u5b87\u591a\u7530\u30d2\u30ab\u30eb"
    )


def test_music_url_cleans_control_characters():
    assert "%00" not in build_music_search_url("a\x00b")
