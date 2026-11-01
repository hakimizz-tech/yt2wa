from pathlib import Path

from fakes.factories import make_facts
from yt2wa.domain.ffmpeg_args import (
    FfmpegPlan,
    build_ffmpeg_args,
    build_video_filter,
    select_h264_level,
    target_size,
)
from yt2wa.domain.models import LadderStep, Method
from yt2wa.domain.profile import DEFAULT_CHAT


def plan(method=Method.TRANSCODE, cap=480, step=None, **facts):
    return FfmpegPlan(
        source=Path("in.mkv"),
        output=Path("out.mp4"),
        method=method,
        facts=make_facts(**facts),
        profile=DEFAULT_CHAT,
        short_cap=cap,
        step=step,
    )


def pairs(args, flag):
    return [args[i + 1] for i, a in enumerate(args) if a == flag]


def test_levels_follow_picture_size():
    assert select_h264_level(854, 480) == "3.0"
    assert select_h264_level(1280, 720) == "3.1"
    assert select_h264_level(1920, 1080) == "4.0"


def test_target_size_never_upscales():
    facts = make_facts(width=640, height=360)
    assert target_size(facts, 480, 1920) == (640, 360)


def test_target_size_scales_landscape_by_short_edge():
    facts = make_facts(width=1920, height=1080)
    assert target_size(facts, 480, 1920) == (854, 480)


def test_target_size_scales_portrait_by_short_edge():
    facts = make_facts(width=1080, height=1920)
    assert target_size(facts, 480, 1920) == (480, 854)


def test_target_size_uses_even_numbers_and_swaps_for_rotation():
    facts = make_facts(width=853, height=481, rotation=90)
    width, height = target_size(facts, 1080, 1920)
    assert width % 2 == 0 and height % 2 == 0
    assert (width, height) == (480, 852)


def test_no_filter_when_nothing_changes():
    facts = make_facts()
    assert build_video_filter(facts, facts.display_size, 30) is None


def test_fps_filter_only_above_the_limit():
    facts = make_facts(fps=60.0)
    assert build_video_filter(facts, facts.display_size, 30) == "fps=30"


def test_transcode_args_follow_the_profile():
    args = build_ffmpeg_args(plan(width=1280, height=720))
    assert pairs(args, "-c:v") == ["libx264"]
    assert pairs(args, "-pix_fmt") == ["yuv420p"]
    assert pairs(args, "-c:a") == ["aac"]
    assert pairs(args, "-profile:a") == ["aac_low"]
    assert pairs(args, "-ac") == ["2"]
    assert pairs(args, "-ar") == ["48000"]
    assert pairs(args, "-movflags") == ["+faststart"]
    assert pairs(args, "-vf") == ["scale=854:480:flags=lanczos"]
    assert pairs(args, "-crf") == ["23"]
    assert args[-1] == "out.mp4"


def test_bitrate_step_sets_the_target_bitrate():
    step = LadderStep("bitrate", 480, 900)
    args = build_ffmpeg_args(plan(step=step))
    assert pairs(args, "-b:v") == ["900k"]
    assert "-crf" not in args


def test_44100_hz_audio_is_kept():
    args = build_ffmpeg_args(plan(sample_rate=44100))
    assert pairs(args, "-ar") == ["44100"]


def test_silent_source_gets_no_audio_track():
    args = build_ffmpeg_args(plan(acodec=None, aprofile=None))
    assert "-an" in args
    assert "-c:a" not in args


def test_remux_copies_streams_and_enables_faststart():
    args = build_ffmpeg_args(plan(method=Method.REMUX))
    assert pairs(args, "-c") == ["copy"]
    assert "libx264" not in args
    assert pairs(args, "-movflags") == ["+faststart"]


def test_command_is_a_list_of_plain_strings():
    args = build_ffmpeg_args(plan())
    assert all(isinstance(a, str) for a in args)
    assert args[0] == "ffmpeg"
