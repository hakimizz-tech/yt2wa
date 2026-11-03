import pytest

from fakes.v03_fakes import make_audio_facts
from yt2wa.domain import compliance as c
from yt2wa.domain.audio_compliance import (
    AUDIO_BITRATE,
    AUDIO_CONTAINER,
    NO_VIDEO,
    check_audio_compliance,
    decide_audio_path,
)
from yt2wa.domain.audio_profile import DEFAULT_AUDIO
from yt2wa.domain.models import AudioFormat, Method

MB = 1024 * 1024


def failed(report):
    return {r.name for r in report.errors}


def check(fmt=AudioFormat.M4A, cap=16 * MB, **overrides):
    facts = make_audio_facts(**overrides)
    return check_audio_compliance(facts, DEFAULT_AUDIO, cap, fmt, 128)


def test_compliant_m4a_passes():
    assert check().ok


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"acodec": "opus"}, c.AUDIO_CODEC),
        ({"aprofile": "HE-AAC"}, c.AUDIO_PROFILE),
        ({"channels": 6}, c.AUDIO_CHANNELS),
        ({"sample_rate": 22050}, c.SAMPLE_RATE),
        ({"abitrate_k": 320}, AUDIO_BITRATE),
        ({"faststart": False}, c.FASTSTART),
        ({"container": "matroska,webm"}, AUDIO_CONTAINER),
        ({"vcodec": "mjpeg"}, NO_VIDEO),
        ({"acodec": None, "aprofile": None}, c.AUDIO_PRESENT),
        ({"size_bytes": 20 * MB}, c.FILE_SIZE),
    ],
)
def test_each_rule_is_detected(overrides, expected):
    assert expected in failed(check(**overrides))


def test_mono_audio_and_unknown_bitrate_are_accepted():
    assert check(channels=1, abitrate_k=None).ok


def test_bitrate_tolerance_allows_a_slightly_higher_rate():
    assert check(abitrate_k=130).ok


def test_mp3_rules():
    ok = check(
        AudioFormat.MP3, container="mp3", acodec="mp3", aprofile=None,
        faststart=None,
    )  # fmt: skip
    assert ok.ok
    wrong = check(AudioFormat.MP3, acodec="aac")
    assert c.AUDIO_CODEC in failed(wrong)


def test_no_size_check_without_a_cap():
    report = check(cap=None, size_bytes=900 * MB)
    assert report.ok


@pytest.mark.parametrize(
    ("overrides", "method"),
    [
        ({}, Method.REMUX),
        ({"faststart": False}, Method.REMUX),
        ({"container": "matroska"}, Method.REMUX),
        ({"acodec": "opus"}, Method.TRANSCODE),
        ({"sample_rate": 22050}, Method.TRANSCODE),
        ({"size_bytes": 30 * MB}, Method.TRANSCODE),
    ],
)
def test_decide_audio_path(overrides, method):
    assert decide_audio_path(check(**overrides)).method is method
