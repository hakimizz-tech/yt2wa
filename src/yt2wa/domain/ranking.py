"""Rank search candidates to find the most likely match. Pure.

The same input always gives the same output. Every number that affects
the result is a named constant so changes are visible in review.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

from yt2wa.domain.models import (
    CandidateOrigin,
    ScoredCandidate,
    SearchCandidate,
    SearchKind,
    SearchResult,
)
from yt2wa.domain.text_rules import (
    normalize_text,
    parse_artist_title,
    tokenize,
)

MUSIC_WEIGHTS = {
    "title": 0.40,
    "coverage": 0.20,
    "source": 0.15,
    "duration": 0.10,
    "position": 0.10,
    "popularity": 0.05,
}
VIDEO_WEIGHTS = {
    "title": 0.45,
    "coverage": 0.20,
    "source": 0.05,
    "duration": 0.00,
    "position": 0.20,
    "popularity": 0.10,
}

ORIGIN_SCORE = {
    CandidateOrigin.MUSIC_TRACK: 1.0,
    CandidateOrigin.OFFICIAL_VIDEO: 0.8,
    CandidateOrigin.UNKNOWN: 0.4,
    CandidateOrigin.USER_UPLOAD: 0.2,
}

# Words that usually mean "not the original". Skipped when the query
# itself contains the phrase.
PENALTIES = (
    ("cover", 0.20),
    ("live", 0.15),
    ("remix", 0.15),
    ("reaction", 0.25),
    ("karaoke", 0.25),
    ("slowed", 0.20),
    ("sped up", 0.20),
    ("nightcore", 0.25),
    ("8d", 0.20),
    ("instrumental", 0.15),
    ("tutorial", 0.25),
    ("review", 0.20),
    ("compilation", 0.20),
    ("loop", 0.15),
    ("1 hour", 0.20),
    ("10 hours", 0.25),
)
MAX_PENALTY = 0.6
LONG_MUSIC_S = 1200
LONG_MUSIC_PENALTY = 0.20
AMBIGUITY_MARGIN = 0.08


def infer_origin(title: str, channel: str) -> CandidateOrigin:
    """Guess the origin of a result from its title and channel."""
    norm_title = normalize_text(title)
    if re.search(r"-\s*topic$", channel.strip(), re.IGNORECASE):
        return CandidateOrigin.MUSIC_TRACK
    if "official audio" in norm_title or "provided to youtube" in norm_title:
        return CandidateOrigin.MUSIC_TRACK
    if (
        "official video" in norm_title
        or "official music video" in norm_title
        or normalize_text(channel).endswith("vevo")
    ):
        return CandidateOrigin.OFFICIAL_VIDEO
    return CandidateOrigin.UNKNOWN


def duration_fit(duration_s: float) -> float:
    """Score how song-like a length is (full credit 90 s to 10 min)."""
    if duration_s <= 0:
        return 0.5
    if duration_s < 30:
        return 0.0
    if duration_s < 90:
        return (duration_s - 30) / 60
    if duration_s <= 600:
        return 1.0
    if duration_s < 1200:
        return (1200 - duration_s) / 600
    return 0.0


def _title_f1(query: set[str], title: set[str]) -> float:
    """Harmonic mean of how much of each side the other covers."""
    hits = len(query & title)
    if not query or not title or hits == 0:
        return 0.0
    precision, recall = hits / len(title), hits / len(query)
    return 2 * precision * recall / (precision + recall)


def _clock(seconds: float) -> str:
    """Format seconds as m:ss."""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


def _penalties(
    query: str, candidate: SearchCandidate, kind: SearchKind
) -> tuple[float, list[str]]:
    """Return the total penalty and the reasons for it."""
    padded_title = f" {normalize_text(candidate.title)} "
    padded_query = f" {normalize_text(query)} "
    total, reasons = 0.0, []
    for phrase, value in PENALTIES:
        marker = f" {phrase} "
        if marker in padded_title and marker not in padded_query:
            total += value
            reasons.append(f"penalty: '{phrase}'")
    if kind is SearchKind.MUSIC and candidate.duration_s > LONG_MUSIC_S:
        total += LONG_MUSIC_PENALTY
        reasons.append("penalty: too long for a song")
    return min(total, MAX_PENALTY), reasons


def _score(
    query: str, candidate: SearchCandidate, kind: SearchKind
) -> ScoredCandidate:
    """Score one candidate."""
    weights = MUSIC_WEIGHTS if kind is SearchKind.MUSIC else VIDEO_WEIGHTS
    query_tokens = set(tokenize(query))
    title_tokens = set(tokenize(candidate.title))
    identity = title_tokens | set(tokenize(candidate.channel))
    for name in candidate.artists:
        identity |= set(tokenize(name))

    features = {
        "title": _title_f1(query_tokens, title_tokens),
        "coverage": (
            len(query_tokens & identity) / len(query_tokens)
            if query_tokens
            else 0.0
        ),
        "source": ORIGIN_SCORE[candidate.origin],
        "duration": duration_fit(candidate.duration_s),
        "position": 1 / (1 + 0.25 * candidate.position),
        "popularity": min(
            1.0, math.log10((candidate.view_count or 0) + 1) / 9
        ),
    }
    penalty, penalty_reasons = _penalties(query, candidate, kind)
    raw = sum(weights[name] * value for name, value in features.items())
    score = round(max(0.0, min(1.0, raw - penalty)), 4)

    reasons = [
        f"title matches {len(query_tokens & title_tokens)}/"
        f"{len(query_tokens)} words"
    ]
    if candidate.origin is CandidateOrigin.MUSIC_TRACK:
        reasons.append("music track source")
    elif candidate.origin is CandidateOrigin.OFFICIAL_VIDEO:
        reasons.append("official video source")
    if kind is SearchKind.MUSIC and features["duration"] == 1.0:
        reasons.append(f"duration {_clock(candidate.duration_s)} fits a song")
    reasons += penalty_reasons

    parsed_artist, track = parse_artist_title(
        candidate.title, candidate.channel
    )
    artist = candidate.artists[0] if candidate.artists else parsed_artist
    return ScoredCandidate(candidate, score, tuple(reasons), artist, track)


def rank_candidates(
    query: str, candidates: Sequence[SearchCandidate], kind: SearchKind
) -> SearchResult:
    """Order candidates by likelihood and report how sure we are."""
    scored = sorted(
        (_score(query, candidate, kind) for candidate in candidates),
        key=lambda item: (-item.score, item.candidate.position),
    )
    if not scored:
        return SearchResult(query, None, (), 0.0, False)
    best, rest = scored[0], tuple(scored[1:])
    ambiguous = bool(rest) and (best.score - rest[0].score) < AMBIGUITY_MARGIN
    return SearchResult(query, best, rest, best.score, ambiguous)
