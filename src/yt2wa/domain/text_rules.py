"""Text helpers for search ranking and audio file names. Pure."""

from __future__ import annotations

import re
import unicodedata

from yt2wa.domain.models import SourceMetadata

# Words that say nothing about which song or video it is.
NOISE_WORDS = frozenset(
    {
        "official",
        "video",
        "audio",
        "music",
        "hd",
        "4k",
        "lyric",
        "lyrics",
        "visualizer",
        "ft",
        "feat",
        "featuring",
        "topic",
        "remastered",
        "remaster",
    }
)

# Words allowed inside a bracket that we strip from the end of a title.
_FILLER_WORDS = NOISE_WORDS | {"hq", "explicit", "song", "mv", "full", "new"}
_SEPARATORS = (" - ", " \u2013 ", " \u2014 ")
_TRAILING_BRACKET = re.compile(r"\s*[(\[]([^()\[\]]*)[)\]]\s*$")
_TOPIC_SUFFIX = re.compile(r"\s*-\s*topic$", re.IGNORECASE)
_VEVO_SUFFIX = re.compile(r"\s*vevo$", re.IGNORECASE)
_MULTIPLIERS = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def normalize_text(text: str) -> str:
    """Lowercase, fold accents and turn punctuation into spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in decomposed if not unicodedata.combining(c))
    spaced = re.sub(r"[^\w\s]|_", " ", folded.lower())
    return " ".join(spaced.split())


def tokenize(text: str) -> list[str]:
    """Split text into words, dropping noise words when possible."""
    words = normalize_text(text).split()
    kept = [word for word in words if word not in NOISE_WORDS]
    return kept or words


def clean_query(query: str, max_len: int = 200) -> str:
    """Remove control characters, squeeze spaces and cap the length."""
    printable = "".join(
        " " if unicodedata.category(c) in ("Cc", "Cf") else c for c in query
    )
    return " ".join(printable.split())[:max_len].strip()


def clean_channel(channel: str) -> str:
    """Turn a channel name into an artist name (drops Topic and VEVO)."""
    name = _TOPIC_SUFFIX.sub("", channel.strip())
    return _VEVO_SUFFIX.sub("", name).strip()


def _strip_filler_brackets(title: str) -> str:
    """Remove trailing brackets such as '(Official Video)'."""
    while True:
        match = _TRAILING_BRACKET.search(title)
        if match is None:
            return title
        words = normalize_text(match.group(1)).split()
        if not words or not all(word in _FILLER_WORDS for word in words):
            return title
        title = title[: match.start()]


def parse_artist_title(
    raw_title: str, channel: str = ""
) -> tuple[str | None, str]:
    """Split a video title into (artist, title).

    Uses the 'Artist - Title' shape when present, otherwise falls back
    to the channel name as the artist.
    """
    title = _strip_filler_brackets(raw_title.strip())
    for separator in _SEPARATORS:
        artist, found, rest = title.partition(separator)
        if found and artist.strip() and rest.strip():
            return artist.strip(), rest.strip()
    return (clean_channel(channel) or None), title.strip()


def parse_duration(text: str | int | float | None) -> int:
    """Turn '3:42' or '1:02:03' into seconds. Returns 0 if unknown."""
    if isinstance(text, (int, float)):
        return max(0, int(text))
    if not text:
        return 0
    parts = text.strip().split(":")
    if not all(part.isdigit() for part in parts) or len(parts) > 3:
        return 0
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def parse_view_count(value: str | int | None) -> int | None:
    """Turn '1.2M views' or '1,234 views' into a number."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"([\d.,]+)\s*([KMBkmb])?", value)
    if match is None:
        return None
    try:
        number = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    factor = _MULTIPLIERS.get((match.group(2) or "").upper(), 1)
    return int(number * factor)


def _one_line(text: str) -> str:
    """Collapse all whitespace so a tag stays on one line."""
    return " ".join(text.split())


def _artist_and_title(meta: SourceMetadata) -> tuple[str | None, str]:
    """Pick the best artist and title we know."""
    parsed_artist, parsed_title = parse_artist_title(
        meta.title, meta.uploader or ""
    )
    return meta.artist or parsed_artist, meta.track or parsed_title


def audio_tags(meta: SourceMetadata) -> dict[str, str]:
    """Return the tags to write into an audio file."""
    artist, title = _artist_and_title(meta)
    tags = {"title": _one_line(title)}
    if artist:
        tags["artist"] = _one_line(artist)
    if meta.album:
        tags["album"] = _one_line(meta.album)
    return tags


def audio_file_stem(meta: SourceMetadata) -> str:
    """Return 'Artist - Title', or just the title when no artist."""
    artist, title = _artist_and_title(meta)
    return f"{artist} - {title}" if artist else title
