from dataclasses import replace
from pathlib import Path

import pytest

from fakes.fakes import FakeDownloader
from fakes.v03_fakes import FakeSearchProvider, make_candidate
from yt2wa.application.dto import ConvertRequest, SearchRequest
from yt2wa.application.search import SearchUseCase
from yt2wa.application.search_chain import ChainedSearchProvider
from yt2wa.domain.errors import (
    NetworkError,
    NotFoundError,
    UsageError,
)
from yt2wa.domain.models import (
    CandidateOrigin,
    ConversionResult,
    MediaKind,
    Method,
    SearchKind,
    SearchProviderName,
    Target,
)

P = SearchProviderName


class StubConvert:
    """Records what it was asked to download."""

    def __init__(self):
        self.requests = []

    def execute(self, request, on_progress=None):
        self.requests.append(request)
        return ConversionResult(
            output=Path("out/file.m4a"),
            target=request.target,
            method=Method.REMUX,
            title="t",
            requested_resolution=request.resolution,
            effective_resolution=0,
            size_bytes=1,
            report=None,
            media=request.media,
        )


class DetailDownloader(FakeDownloader):
    """Fails when asked for details."""

    def probe(self, ref):
        raise NetworkError("no details")


GOOD = make_candidate(
    "aaaaaaaaaaa", "Daft Punk - One More Time (Official Video)",
    "Daft Punk", 320, 600_000_000, 0, CandidateOrigin.OFFICIAL_VIDEO,
)  # fmt: skip
OTHER = make_candidate(
    "bbbbbbbbbbb", "Something unrelated entirely", "X", 100, 5, 1
)


def build(results, downloader=None):
    provider = FakeSearchProvider(results)
    gateway = ChainedSearchProvider({P.YTSEARCH: provider})
    convert = StubConvert()
    usecase = SearchUseCase(gateway, downloader or FakeDownloader(), convert)
    return usecase, provider, convert


def download_request(tmp_path):
    return ConvertRequest(
        url="",
        target=Target.CHAT,
        resolution=480,
        output_dir=tmp_path,
        media=MediaKind.AUDIO,
    )


def test_returns_the_ranked_best_match_and_alternates():
    usecase, _, _ = build([OTHER, GOOD])
    outcome = usecase.execute(SearchRequest("daft punk one more time"))
    best = outcome.result.best
    assert best is not None
    assert best.candidate.video_id == "aaaaaaaaaaa"
    assert [a.candidate.video_id for a in outcome.result.alternates] == [
        "bbbbbbbbbbb"
    ]
    assert outcome.result.provider is P.YTSEARCH
    assert outcome.conversion is None


def test_nothing_found_is_a_not_found_error_naming_the_methods_tried():
    usecase, _, _ = build([])
    with pytest.raises(NotFoundError) as info:
        usecase.execute(SearchRequest("zzzz"))
    assert "ytsearch" in (info.value.hint or "")


def test_empty_query_is_a_usage_error():
    usecase, provider, _ = build([GOOD])
    with pytest.raises(UsageError):
        usecase.execute(SearchRequest("  \x00 "))
    assert provider.calls == []


def test_limit_is_clamped_to_the_maximum():
    usecase, provider, _ = build([GOOD])
    usecase.execute(SearchRequest("daft punk", limit=999))
    usecase.execute(SearchRequest("daft punk", limit=0))
    assert [call[2] for call in provider.calls] == [25, 1]


def test_download_uses_the_canonical_url_and_keeps_the_request(tmp_path):
    usecase, _, convert = build([GOOD])
    outcome = usecase.execute(
        SearchRequest(
            "daft punk one more time",
            kind=SearchKind.MUSIC,
            download=download_request(tmp_path),
        )
    )
    sent = convert.requests[0]
    assert sent.url == "https://www.youtube.com/watch?v=aaaaaaaaaaa"
    assert sent.media is MediaKind.AUDIO
    assert outcome.conversion is not None


def test_download_is_refused_below_the_confidence_threshold(tmp_path):
    usecase, _, convert = build([OTHER])
    with pytest.raises(NotFoundError):
        usecase.execute(
            SearchRequest("daft punk", download=download_request(tmp_path))
        )
    assert convert.requests == []


def test_download_is_refused_when_the_result_is_ambiguous(tmp_path):
    twins = [
        make_candidate("aaaaaaaaaaa", "Artist - Song", position=0),
        make_candidate("bbbbbbbbbbb", "Artist - Song", position=1),
    ]
    usecase, _, convert = build(twins)
    request = SearchRequest(
        "artist song", min_confidence=0.1, download=download_request(tmp_path)
    )
    with pytest.raises(NotFoundError) as info:
        usecase.execute(request)
    assert "--pick" in (info.value.hint or "")
    assert convert.requests == []


def test_pick_chooses_an_alternate_even_when_ambiguous(tmp_path):
    twins = [
        make_candidate("aaaaaaaaaaa", "Artist - Song", position=0),
        make_candidate("bbbbbbbbbbb", "Artist - Song", position=1),
    ]
    usecase, _, convert = build(twins)
    usecase.execute(
        SearchRequest(
            "artist song", pick=2, download=download_request(tmp_path)
        )
    )
    assert convert.requests[0].url.endswith("bbbbbbbbbbb")


def test_pick_out_of_range_is_a_usage_error(tmp_path):
    usecase, _, convert = build([GOOD])
    with pytest.raises(UsageError):
        usecase.execute(
            SearchRequest(
                "daft punk", pick=3, download=download_request(tmp_path)
            )
        )
    assert convert.requests == []


def test_detail_failure_is_a_note_not_an_error():
    usecase, _, _ = build([GOOD], DetailDownloader())
    outcome = usecase.execute(SearchRequest("daft punk", detail=True))
    assert outcome.detail is None
    assert len(outcome.notes) == 1


def test_detail_adds_metadata_when_available():
    usecase, _, _ = build([GOOD])
    outcome = usecase.execute(SearchRequest("daft punk", detail=True))
    assert outcome.detail is not None
    assert outcome.detail.title == "My Clip"


def test_the_download_request_is_not_mutated(tmp_path):
    usecase, _, _ = build([GOOD])
    original = download_request(tmp_path)
    usecase.execute(SearchRequest("daft punk", download=original))
    assert original == replace(original, url="")
