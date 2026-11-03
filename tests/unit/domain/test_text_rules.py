import pytest

from yt2wa.domain.models import SourceMetadata
from yt2wa.domain.text_rules import (
    audio_file_stem,
    audio_tags,
    clean_channel,
    clean_query,
    normalize_text,
    parse_artist_title,
    parse_duration,
    parse_view_count,
    tokenize,
)


def test_normalize_folds_accents_case_and_punctuation():
    assert normalize_text("  Beyonc\u00e9 -- HALO!! ") == "beyonce halo"


def test_tokenize_drops_noise_words():
    assert tokenize("Daft Punk - One More Time (Official Video)") == [
        "daft", "punk", "one", "more", "time",
    ]  # fmt: skip


def test_tokenize_keeps_words_when_everything_is_noise():
    assert tokenize("official video") == ["official", "video"]


def test_clean_query_strips_control_characters_and_caps_length():
    assert clean_query("a\x00b\n\tc  d") == "a b c d"
    assert len(clean_query("x" * 500)) == 200


@pytest.mark.parametrize(
    ("raw", "channel", "expected"),
    [
        (
            "Daft Punk - One More Time (Official Video)",
            "",
            ("Daft Punk", "One More Time"),
        ),
        (
            "Queen \u2013 Bohemian Rhapsody [HD]",
            "",
            ("Queen", "Bohemian Rhapsody"),
        ),
        ("Hello", "Adele - Topic", ("Adele", "Hello")),
        ("Hello", "AdeleVEVO", ("Adele", "Hello")),
        ("Hello", "", (None, "Hello")),
        ("Song (Live at Wembley)", "", (None, "Song (Live at Wembley)")),
        ("Artist - Song (Official Audio) (HD)", "", ("Artist", "Song")),
    ],
)  # fmt: skip
def test_parse_artist_title(raw, channel, expected):
    assert parse_artist_title(raw, channel) == expected


def test_clean_channel():
    assert clean_channel("Daft Punk - Topic") == "Daft Punk"
    assert clean_channel("  PsyVEVO ") == "Psy"


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("3:42", 222), ("1:02:03", 3723), ("45", 45), ("", 0), ("abc", 0),
     (None, 0), (200, 200), ("1:2:3:4", 0)],
)  # fmt: skip
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize(
    ("text", "count"),
    [("1.2M views", 1_200_000), ("1,234 views", 1234), ("3K", 3000),
     ("2B views", 2_000_000_000), (None, None), ("no views", None),
     (77, 77)],
)  # fmt: skip
def test_parse_view_count(text, count):
    assert parse_view_count(text) == count


def test_audio_tags_prefer_real_metadata():
    meta = SourceMetadata(
        "abcdefghijk", "x - y", 10, "Chan", artist="A", track="T", album="Al"
    )
    assert audio_tags(meta) == {"title": "T", "artist": "A", "album": "Al"}
    assert audio_file_stem(meta) == "A - T"


def test_audio_tags_fall_back_to_the_title():
    meta = SourceMetadata(
        "abcdefghijk", "Daft Punk - One More Time (Official Video)", 10
    )
    assert audio_tags(meta) == {
        "title": "One More Time",
        "artist": "Daft Punk",
    }
    assert audio_file_stem(meta) == "Daft Punk - One More Time"


def test_audio_file_stem_without_an_artist():
    meta = SourceMetadata("abcdefghijk", "Just A Title", 10)
    assert audio_file_stem(meta) == "Just A Title"
