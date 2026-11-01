import pytest

from yt2wa.domain.errors import UsageError
from yt2wa.domain.formats import (
    build_format_selector,
    parse_resolution,
    short_edge_cap,
)
from yt2wa.domain.models import BEST_RESOLUTION, Target


@pytest.mark.parametrize(
    ("text", "expected"),
    [("480", 480), ("720p", 720), (" BEST ", BEST_RESOLUTION)],
)
def test_parse_resolution(text, expected):
    assert parse_resolution(text) == expected


@pytest.mark.parametrize("text", ["420", "760", "abc", "", "4k"])
def test_parse_resolution_rejects_unknown_values(text):
    with pytest.raises(UsageError):
        parse_resolution(text)


def test_original_best_has_no_cap():
    assert short_edge_cap(Target.ORIGINAL, BEST_RESOLUTION, 1080) is None


def test_shareable_best_is_clamped_to_profile_maximum():
    assert short_edge_cap(Target.CHAT, BEST_RESOLUTION, 1080) == 1080


def test_cap_never_exceeds_profile_maximum():
    assert short_edge_cap(Target.STATUS, 1080, 720) == 720


def test_selector_prefers_h264_and_aac_within_the_cap():
    choice = build_format_selector(Target.CHAT, 480)
    assert choice.sort == ("res:480", "vcodec:h264", "acodec:aac")
    assert choice.selector == "bv*+ba/b"


def test_original_best_selector_has_no_limit():
    choice = build_format_selector(Target.ORIGINAL, BEST_RESOLUTION)
    assert choice.sort[0] == "res"
