import pytest

from yt2wa.domain.models import SourceKind
from yt2wa.domain.url_rules import classify_url, sanitize_filename


@pytest.mark.parametrize(
    ("url", "kind", "video_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", SourceKind.VIDEO,
         "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", SourceKind.VIDEO, "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/abcdefghijk", SourceKind.SHORT,
         "abcdefghijk"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1",
         SourceKind.VIDEO, "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", SourceKind.VIDEO,
         "dQw4w9WgXcQ"),
    ],
)
def test_supported_links(url, kind, video_id):
    ref = classify_url(url)
    assert ref.kind is kind
    assert ref.video_id == video_id


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/post/UgkxABC",
        "https://www.youtube.com/@channel/community",
        "https://www.youtube.com/watch",
        "https://vimeo.com/12345",
        "not a url",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_unsupported_links(url):
    assert classify_url(url).kind is SourceKind.UNSUPPORTED


def test_sanitize_filename_removes_unsafe_characters():
    assert sanitize_filename('a/b:c*"d?  e') == "abcd_e"


def test_sanitize_filename_falls_back_for_empty_names():
    assert sanitize_filename("///") == "video"
    assert sanitize_filename("CON") == "video"


def test_sanitize_filename_limits_length():
    assert len(sanitize_filename("x" * 500)) <= 80
