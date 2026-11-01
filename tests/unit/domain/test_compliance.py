import pytest

from fakes.factories import make_facts
from yt2wa.domain import compliance as c
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.profile import DEFAULT_CHAT, DEFAULT_STATUS

MB = 1024 * 1024


def failed_names(report):
    return {r.name for r in report.errors}


def test_compliant_file_passes_every_check():
    report = check_compliance(make_facts(), DEFAULT_CHAT, 16 * MB)
    assert report.ok
    assert not report.failed


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"vcodec": "vp9"}, c.VIDEO_CODEC),
        ({"pix_fmt": "yuv444p"}, c.PIXEL_FORMAT),
        ({"fps": 60.0}, c.FRAME_RATE),
        ({"acodec": "opus"}, c.AUDIO_CODEC),
        ({"aprofile": "HE-AAC"}, c.AUDIO_PROFILE),
        ({"channels": 1}, c.AUDIO_CHANNELS),
        ({"sample_rate": 22050}, c.SAMPLE_RATE),
        ({"faststart": False}, c.FASTSTART),
        ({"faststart": None}, c.FASTSTART),
        ({"rotation": 90}, c.ORIENTATION),
        ({"container": "matroska,webm"}, c.CONTAINER),
        ({"width": 3840, "height": 2160}, c.RESOLUTION),
        ({"vprofile": "High 4:4:4 Predictive"}, c.VIDEO_PROFILE),
        ({"vlevel": 52}, c.VIDEO_LEVEL),
    ],
)
def test_each_rule_is_detected(overrides, expected):
    report = check_compliance(make_facts(**overrides), DEFAULT_CHAT)
    assert expected in failed_names(report)


def test_44100_hz_audio_is_accepted():
    report = check_compliance(
        make_facts(sample_rate=44100), DEFAULT_CHAT
    )
    assert report.ok


def test_size_cap_is_enforced():
    facts = make_facts(size_bytes=20 * MB)
    report = check_compliance(facts, DEFAULT_CHAT, 16 * MB)
    assert failed_names(report) == {c.FILE_SIZE}


def test_missing_audio_is_only_a_warning():
    report = check_compliance(
        make_facts(acodec=None, aprofile=None, channels=None,
                   sample_rate=None),
        DEFAULT_CHAT,
    )
    assert report.ok
    assert [r.name for r in report.warnings] == [c.AUDIO_PRESENT]


def test_landscape_status_gets_an_aspect_warning_not_an_error():
    report = check_compliance(make_facts(), DEFAULT_STATUS)
    assert report.ok
    assert c.ASPECT_RATIO in {r.name for r in report.warnings}


def test_portrait_status_has_no_aspect_warning():
    facts = make_facts(width=480, height=854)
    report = check_compliance(facts, DEFAULT_STATUS)
    assert c.ASPECT_RATIO not in {r.name for r in report.warnings}


def test_short_cap_lowers_the_allowed_resolution():
    facts = make_facts(width=1280, height=720)
    report = check_compliance(facts, DEFAULT_CHAT, short_cap=480)
    assert c.RESOLUTION in failed_names(report)


def test_changed_aspect_ratio_is_detected():
    facts = make_facts(width=640, height=480)
    report = check_compliance(facts, DEFAULT_CHAT, source_aspect=16 / 9)
    assert c.ASPECT_PRESERVED in failed_names(report)
