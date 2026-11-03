"""Every search method must behave the same way, using recorded data."""

import inspect
import json
from pathlib import Path

import pytest

from fakes.v03_fakes import FakeSearchProvider, make_candidate
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
from yt2wa.domain.search_providers import build_music_search_url
from yt2wa.infrastructure.ytdlp_search import (
    YtDlpSearchProvider,
    candidate_from_flat_entry,
)
from yt2wa.infrastructure.ytmusicapi_search import (
    YtMusicApiSearchProvider,
    candidate_from_ytmusic_item,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "search"
FLAT = json.loads((FIXTURES / "ytsearch_flat.json").read_text("utf-8"))
ITEMS = json.loads((FIXTURES / "ytmusicapi_items.json").read_text("utf-8"))
P = SearchProviderName


class FakeClient:
    """Stands in for ytmusicapi.YTMusic."""

    def __init__(self, items=None, error=None):
        self.items, self.error, self.calls = items or [], error, []

    def search(self, query, filter=None, limit=20):  # noqa: A002
        self.calls.append((query, filter, limit))
        if self.error:
            raise self.error
        return self.items


def ytdlp(mode, record=None):
    def extractor(target, options):
        if record is not None:
            record.append((target, options))
        return FLAT

    return YtDlpSearchProvider(mode, extractor=extractor)


def make(name):
    if name == "ytsearch":
        return ytdlp(P.YTSEARCH), P.YTSEARCH
    if name == "ytmusic-url":
        return ytdlp(P.YTMUSIC_URL), P.YTMUSIC_URL
    client = FakeClient(ITEMS)
    return YtMusicApiSearchProvider(lambda: client), P.YTMUSICAPI


@pytest.fixture(params=["ytsearch", "ytmusic-url", "ytmusicapi"])
def provider(request):
    return make(request.param)


def test_returns_candidates_in_a_common_shape(provider):
    instance, name = provider
    found = instance.search("one more time", SearchKind.MUSIC, 10)
    assert found
    assert all(isinstance(c, SearchCandidate) for c in found)
    assert all(c.provider is name for c in found)
    assert [c.position for c in found] == list(range(len(found)))


def test_ids_are_unique_and_urls_are_canonical(provider):
    instance, _ = provider
    found = instance.search("one more time", SearchKind.MUSIC, 10)
    ids = [c.video_id for c in found]
    assert len(ids) == len(set(ids))
    for c in found:
        assert c.url == f"https://www.youtube.com/watch?v={c.video_id}"
        assert len(c.video_id) == 11


def test_the_limit_is_respected(provider):
    instance, _ = provider
    assert len(instance.search("one more time", SearchKind.ANY, 1)) == 1


def test_entries_without_a_video_id_are_skipped():
    found = ytdlp(P.YTSEARCH).search("x", SearchKind.ANY, 10)
    assert [c.video_id for c in found] == [
        "aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"
    ]  # fmt: skip
    api = YtMusicApiSearchProvider(lambda: FakeClient(ITEMS))
    ids = [c.video_id for c in api.search("x", SearchKind.MUSIC, 10)]
    assert ids == [
        "aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc", "ddddddddddd"
    ]  # fmt: skip


def test_ytsearch_uses_the_search_prefix_and_flat_extraction():
    record = []
    ytdlp(P.YTSEARCH, record).search("  daft\npunk ", SearchKind.ANY, 5)
    target, options = record[0]
    assert target == "ytsearch5:daft punk"
    assert options["extract_flat"] is True
    assert options["skip_download"] is True


def test_music_url_mode_loads_the_music_search_page():
    record = []
    ytdlp(P.YTMUSIC_URL, record).search("daft punk", SearchKind.MUSIC, 5)
    assert record[0][0] == build_music_search_url("daft punk")


def test_yt_dlp_origin_is_inferred_from_title_and_channel():
    found = ytdlp(P.YTSEARCH).search("x", SearchKind.ANY, 10)
    origins = {c.video_id: c.origin for c in found}
    assert origins["aaaaaaaaaaa"] is CandidateOrigin.OFFICIAL_VIDEO
    assert origins["ccccccccccc"] is CandidateOrigin.MUSIC_TRACK
    assert origins["bbbbbbbbbbb"] is CandidateOrigin.UNKNOWN


def test_ytmusicapi_mapping_keeps_rich_metadata():
    found = YtMusicApiSearchProvider(lambda: FakeClient(ITEMS)).search(
        "x", SearchKind.MUSIC, 10
    )
    first, second, third, fourth = found
    assert first.origin is CandidateOrigin.MUSIC_TRACK
    assert first.artists == ("Daft Punk",)
    assert first.album == "Discovery"
    assert first.duration_s == 320
    assert second.album is None
    assert second.duration_s == 232
    assert third.origin is CandidateOrigin.OFFICIAL_VIDEO
    assert third.view_count == 612_000_000
    assert fourth.origin is CandidateOrigin.USER_UPLOAD
    assert fourth.duration_s == 3723
    assert fourth.view_count == 1234


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (SearchKind.MUSIC, "songs"),
        (SearchKind.VIDEO, "videos"),
        (SearchKind.ANY, None),
    ],
)
def test_ytmusicapi_filter_follows_the_search_kind(kind, expected):
    client = FakeClient(ITEMS)
    YtMusicApiSearchProvider(lambda: client).search("q  q", kind, 4)
    assert client.calls == [("q q", expected, 4)]


def test_ytmusicapi_client_is_created_once():
    made = []

    def factory():
        made.append(1)
        return FakeClient(ITEMS)

    api = YtMusicApiSearchProvider(factory)
    api.search("a", SearchKind.MUSIC, 3)
    api.search("b", SearchKind.MUSIC, 3)
    assert len(made) == 1


def test_ytmusicapi_errors_become_domain_errors():
    network = YtMusicApiSearchProvider(
        lambda: FakeClient(error=ConnectionError("down"))
    )
    with pytest.raises(NetworkError):
        network.search("x", SearchKind.MUSIC, 3)
    broken = YtMusicApiSearchProvider(
        lambda: FakeClient(error=KeyError("contents"))
    )
    with pytest.raises(SourceUnavailableError):
        broken.search("x", SearchKind.MUSIC, 3)


def test_missing_ytmusicapi_is_a_dependency_error():
    def missing():
        raise MissingBinaryError("not installed")

    with pytest.raises(MissingBinaryError):
        YtMusicApiSearchProvider(missing).search("x", SearchKind.MUSIC, 3)


def test_empty_answers_are_empty_lists():
    assert (
        YtMusicApiSearchProvider(lambda: FakeClient([])).search(
            "x", SearchKind.MUSIC, 3
        )
        == []
    )
    empty = YtDlpSearchProvider(
        P.YTSEARCH, extractor=lambda target, options: {"entries": []}
    )
    assert empty.search("x", SearchKind.ANY, 3) == []


def test_yt_dlp_provider_rejects_other_modes():
    with pytest.raises(ValueError):
        YtDlpSearchProvider(P.YTMUSICAPI)


def test_mapper_functions_skip_garbage():
    assert candidate_from_flat_entry({}, 0, P.YTSEARCH) is None
    assert candidate_from_ytmusic_item({"videoId": 5}, 0) is None
    assert candidate_from_ytmusic_item({"videoId": "short"}, 0) is None


def test_fake_provider_follows_the_same_port():
    found = FakeSearchProvider([make_candidate()]).search(
        "x", SearchKind.ANY, 3
    )
    assert found[0].video_id == "aaaaaaaaaaa"


def test_the_real_library_still_has_the_search_signature_we_use():
    pytest.importorskip("ytmusicapi")
    from ytmusicapi import YTMusic

    params = inspect.signature(YTMusic.search).parameters
    assert {"query", "filter", "limit"} <= set(params)
