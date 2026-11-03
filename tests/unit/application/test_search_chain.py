import pytest

from fakes.v03_fakes import FakeSearchProvider, make_candidate
from yt2wa.application.search_chain import ChainedSearchProvider
from yt2wa.domain.errors import (
    MissingBinaryError,
    NetworkError,
    SourceUnavailableError,
)
from yt2wa.domain.models import SearchKind, SearchProviderName

P = SearchProviderName
HIT = [make_candidate()]


def chain(api=None, url=None, plain=None):
    providers = {
        P.YTMUSICAPI: api or FakeSearchProvider(HIT),
        P.YTMUSIC_URL: url or FakeSearchProvider(HIT),
        P.YTSEARCH: plain or FakeSearchProvider(HIT),
    }
    return ChainedSearchProvider(providers), providers


def outcomes(response):
    return [(a.provider, a.outcome) for a in response.attempts]


def test_first_method_that_succeeds_wins_and_others_are_not_called():
    gateway, providers = chain()
    response = gateway.search("q", SearchKind.MUSIC, 5, None)
    assert response.provider is P.YTMUSICAPI
    assert outcomes(response) == [(P.YTMUSICAPI, "ok")]
    assert providers[P.YTMUSIC_URL].calls == []
    assert providers[P.YTSEARCH].calls == []


def test_falls_back_when_the_best_method_fails():
    gateway, _ = chain(api=FakeSearchProvider(error=NetworkError("down")))
    response = gateway.search("q", SearchKind.MUSIC, 5, None)
    assert response.provider is P.YTMUSIC_URL
    assert outcomes(response) == [
        (P.YTMUSICAPI, "error"),
        (P.YTMUSIC_URL, "ok"),
    ]


def test_falls_back_when_a_method_finds_nothing():
    gateway, _ = chain(api=FakeSearchProvider([]), url=FakeSearchProvider([]))
    response = gateway.search("q", SearchKind.MUSIC, 5, None)
    assert response.provider is P.YTSEARCH
    assert outcomes(response) == [
        (P.YTMUSICAPI, "empty"),
        (P.YTMUSIC_URL, "empty"),
        (P.YTSEARCH, "ok"),
    ]


def test_missing_optional_dependency_is_skipped_in_auto_mode():
    missing = FakeSearchProvider(error=MissingBinaryError("no ytmusicapi"))
    gateway, _ = chain(api=missing)
    response = gateway.search("q", SearchKind.MUSIC, 5, None)
    assert outcomes(response)[0] == (P.YTMUSICAPI, "skipped")
    assert response.provider is P.YTMUSIC_URL


def test_missing_dependency_is_fatal_when_the_method_is_explicit():
    missing = FakeSearchProvider(error=MissingBinaryError("no ytmusicapi"))
    gateway, providers = chain(api=missing)
    with pytest.raises(MissingBinaryError):
        gateway.search("q", SearchKind.MUSIC, 5, P.YTMUSICAPI)
    assert providers[P.YTSEARCH].calls == []


def test_explicit_method_never_falls_back_on_error_or_empty():
    gateway, providers = chain(api=FakeSearchProvider(error=NetworkError("x")))
    with pytest.raises(NetworkError):
        gateway.search("q", SearchKind.MUSIC, 5, P.YTMUSICAPI)
    empty, providers = chain(api=FakeSearchProvider([]))
    response = empty.search("q", SearchKind.MUSIC, 5, P.YTMUSICAPI)
    assert response.candidates == ()
    assert providers[P.YTSEARCH].calls == []


def test_video_and_any_searches_use_plain_youtube_search_only():
    for kind in (SearchKind.VIDEO, SearchKind.ANY):
        gateway, providers = chain()
        response = gateway.search("q", kind, 5, None)
        assert response.provider is P.YTSEARCH
        assert providers[P.YTMUSICAPI].calls == []


def test_every_method_failing_reports_the_last_error():
    boom = SourceUnavailableError("boom")
    gateway, _ = chain(
        api=FakeSearchProvider(error=NetworkError("a")),
        url=FakeSearchProvider(error=NetworkError("b")),
        plain=FakeSearchProvider(error=boom),
    )
    with pytest.raises(SourceUnavailableError):
        gateway.search("q", SearchKind.MUSIC, 5, None)


def test_a_real_empty_answer_beats_earlier_errors():
    gateway, _ = chain(
        api=FakeSearchProvider(error=NetworkError("a")),
        url=FakeSearchProvider([]),
        plain=FakeSearchProvider([]),
    )
    response = gateway.search("q", SearchKind.MUSIC, 5, None)
    assert response.candidates == ()
    assert response.provider is None


def test_unconfigured_method_is_skipped():
    gateway = ChainedSearchProvider({P.YTSEARCH: FakeSearchProvider(HIT)})
    response = gateway.search("q", SearchKind.MUSIC, 5, None)
    assert response.provider is P.YTSEARCH
    assert outcomes(response)[0] == (P.YTMUSICAPI, "skipped")


def test_limit_and_query_reach_the_provider():
    plain = FakeSearchProvider(HIT)
    gateway, _ = chain(plain=plain)
    gateway.search("daft punk", SearchKind.VIDEO, 7, None)
    assert plain.calls == [("daft punk", SearchKind.VIDEO, 7)]
