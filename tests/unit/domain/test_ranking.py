import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fakes.v03_fakes import make_candidate
from yt2wa.domain.models import (
    CandidateOrigin,
    SearchCandidate,
    SearchKind,
    SearchProviderName,
)
from yt2wa.domain.ranking import (
    MUSIC_WEIGHTS,
    VIDEO_WEIGHTS,
    duration_fit,
    infer_origin,
    rank_candidates,
)

CASES = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "search"
        / "ranking_cases.json"
    ).read_text(encoding="utf-8")
)


def build(case):
    return [
        SearchCandidate(
            video_id=c["video_id"],
            url=f"https://www.youtube.com/watch?v={c['video_id']}",
            title=c["title"],
            channel=c["channel"],
            duration_s=c["duration_s"],
            view_count=c["view_count"],
            position=c["position"],
            origin=CandidateOrigin(c["origin"]),
            provider=SearchProviderName.YTSEARCH,
            artists=tuple(c["artists"]),
        )
        for c in case["candidates"]
    ]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden_cases(case):
    result = rank_candidates(
        case["query"], build(case), SearchKind(case["kind"])
    )
    assert result.best is not None
    assert result.best.candidate.video_id == case["expected_best"]


def test_weights_add_up_to_one():
    assert sum(MUSIC_WEIGHTS.values()) == pytest.approx(1.0)
    assert sum(VIDEO_WEIGHTS.values()) == pytest.approx(1.0)


def test_empty_list_means_nothing_found():
    result = rank_candidates("anything", [], SearchKind.ANY)
    assert result.best is None
    assert result.alternates == ()
    assert result.confidence == 0.0
    assert not result.ambiguous


def test_near_identical_results_are_ambiguous():
    twins = [
        make_candidate("aaaaaaaaaaa", "Artist - Song", position=0),
        make_candidate("bbbbbbbbbbb", "Artist - Song", position=1),
    ]
    result = rank_candidates("artist song", twins, SearchKind.MUSIC)
    assert result.ambiguous
    assert result.best is not None
    assert result.best.candidate.video_id == "aaaaaaaaaaa"


def test_clear_winner_is_not_ambiguous():
    items = [
        make_candidate("aaaaaaaaaaa", "Artist - Song", position=0),
        make_candidate("bbbbbbbbbbb", "Completely different", position=1),
    ]
    assert not rank_candidates(
        "artist song", items, SearchKind.MUSIC
    ).ambiguous


def test_reasons_explain_the_choice():
    item = make_candidate(
        title="Artist - Song (Official Video)",
        origin=CandidateOrigin.OFFICIAL_VIDEO,
    )
    best = rank_candidates("artist song", [item], SearchKind.MUSIC).best
    assert best is not None
    assert "official video source" in best.reasons
    assert best.artist == "Artist"
    assert best.track == "Song"


def test_artist_from_the_provider_wins_over_the_title():
    item = make_candidate(
        title="Hello", channel="Adele", artists=("Adele",),
        origin=CandidateOrigin.MUSIC_TRACK,
    )  # fmt: skip
    best = rank_candidates("adele hello", [item], SearchKind.MUSIC).best
    assert best is not None
    assert (best.artist, best.track) == ("Adele", "Hello")


def test_ranking_is_deterministic():
    case = CASES[0]
    first = rank_candidates(case["query"], build(case), SearchKind.MUSIC)
    second = rank_candidates(case["query"], build(case), SearchKind.MUSIC)
    assert first == second


def test_noise_words_in_the_query_do_not_change_the_order():
    case = CASES[0]
    plain = rank_candidates(
        "daft punk one more time", build(case), SearchKind.MUSIC
    )
    noisy = rank_candidates(
        "daft punk one more time official video hd",
        build(case),
        SearchKind.MUSIC,
    )
    order = lambda r: [  # noqa: E731
        s.candidate.video_id
        for s in (r.best, *r.alternates)  # type: ignore[union-attr]
    ]
    assert order(plain) == order(noisy)


@pytest.mark.parametrize(
    ("title", "channel", "expected"),
    [
        ("One More Time", "Daft Punk - Topic", CandidateOrigin.MUSIC_TRACK),
        ("Song (Official Audio)", "Someone", CandidateOrigin.MUSIC_TRACK),
        ("Song (Official Video)", "Someone", CandidateOrigin.OFFICIAL_VIDEO),
        ("Song", "ArtistVEVO", CandidateOrigin.OFFICIAL_VIDEO),
        ("Song", "Random", CandidateOrigin.UNKNOWN),
    ],
)
def test_infer_origin(title, channel, expected):
    assert infer_origin(title, channel) is expected


def test_duration_fit_curve():
    assert duration_fit(0) == 0.5
    assert duration_fit(10) == 0.0
    assert duration_fit(60) == pytest.approx(0.5)
    assert duration_fit(200) == 1.0
    assert duration_fit(900) == pytest.approx(0.5)
    assert duration_fit(5000) == 0.0


texts = st.text(min_size=0, max_size=40)


@given(
    query=texts,
    titles=st.lists(texts, min_size=0, max_size=6),
    duration=st.floats(min_value=0, max_value=100_000),
    kind=st.sampled_from(list(SearchKind)),
)
def test_scores_always_stay_between_zero_and_one(
    query, titles, duration, kind
):
    items = [
        make_candidate(f"{i:011d}", title, position=i, duration_s=duration)
        for i, title in enumerate(titles)
    ]
    result = rank_candidates(query, items, kind)
    everything = (
        [] if result.best is None else [result.best, *result.alternates]
    )
    assert len(everything) == len(items)
    scores = [s.score for s in everything]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)
