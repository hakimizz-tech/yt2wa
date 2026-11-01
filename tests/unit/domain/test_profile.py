import pytest

from yt2wa.domain.errors import ConfigError
from yt2wa.domain.models import Target
from yt2wa.domain.profile import (
    DEFAULT_PROFILES,
    profile_for,
    profile_from_mapping,
)


def test_original_target_borrows_the_chat_profile():
    assert profile_for(Target.ORIGINAL, DEFAULT_PROFILES).name == "chat"


def test_override_keeps_other_defaults():
    profile = profile_from_mapping("chat", {"crf": 28})
    assert profile.crf == 28
    assert profile.max_short_edge == 1080


def test_bitrate_tables_are_converted_to_int_keys():
    profile = profile_from_mapping(
        "chat", {"min_video_bitrate_k": {"480": 300}}
    )
    assert profile.min_video_bitrate_k == {480: 300}


def test_unknown_setting_is_rejected():
    with pytest.raises(ConfigError):
        profile_from_mapping("chat", {"colour": "red"})
