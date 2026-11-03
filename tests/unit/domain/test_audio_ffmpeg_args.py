from pathlib import Path

from fakes.v03_fakes import make_audio_facts
from yt2wa.domain.audio_ffmpeg_args import AudioPlan, build_audio_ffmpeg_args
from yt2wa.domain.audio_profile import DEFAULT_AUDIO
from yt2wa.domain.models import AudioFormat, Method


def plan(method=Method.TRANSCODE, fmt=AudioFormat.M4A, **kw):
    facts = kw.pop("facts", make_audio_facts())
    return AudioPlan(
        source=Path("in.webm"),
        output=Path("out." + fmt.value),
        method=method,
        facts=facts,
        profile=DEFAULT_AUDIO,
        audio_format=fmt,
        bitrate_k=kw.pop("bitrate_k", 128),
        **kw,
    )


def values(args, flag):
    return [args[i + 1] for i, a in enumerate(args) if a == flag]


def test_m4a_transcode_uses_aac_lc_and_faststart():
    args = build_audio_ffmpeg_args(plan())
    assert "-vn" in args
    assert values(args, "-c:a") == ["aac"]
    assert values(args, "-profile:a") == ["aac_low"]
    assert values(args, "-b:a") == ["128k"]
    assert values(args, "-ac") == ["2"]
    assert values(args, "-movflags") == ["+faststart"]
    assert args[-1] == "out.m4a"


def test_sample_rate_44100_is_kept_otherwise_48000():
    keep = build_audio_ffmpeg_args(
        plan(facts=make_audio_facts(sample_rate=44100))
    )
    assert values(keep, "-ar") == ["44100"]
    other = build_audio_ffmpeg_args(
        plan(facts=make_audio_facts(sample_rate=24000))
    )
    assert values(other, "-ar") == ["48000"]


def test_mono_stays_mono_and_surround_becomes_stereo():
    mono = build_audio_ffmpeg_args(plan(facts=make_audio_facts(channels=1)))
    assert values(mono, "-ac") == ["1"]
    surround = build_audio_ffmpeg_args(
        plan(facts=make_audio_facts(channels=6))
    )
    assert values(surround, "-ac") == ["2"]


def test_remux_copies_the_audio():
    args = build_audio_ffmpeg_args(plan(method=Method.REMUX))
    assert values(args, "-c:a") == ["copy"]
    assert "-b:a" not in args
    assert values(args, "-movflags") == ["+faststart"]


def test_mp3_uses_lame_and_no_faststart():
    args = build_audio_ffmpeg_args(plan(fmt=AudioFormat.MP3, bitrate_k=96))
    assert values(args, "-c:a") == ["libmp3lame"]
    assert values(args, "-b:a") == ["96k"]
    assert "-movflags" not in args
    assert values(args, "-id3v2_version") == ["3"]
    assert args[-1] == "out.mp3"


def test_tags_are_written_and_source_metadata_is_dropped():
    args = build_audio_ffmpeg_args(
        plan(tags={"title": "One More Time", "artist": "Daft Punk"})
    )
    assert values(args, "-map_metadata") == ["-1"]
    assert values(args, "-metadata") == [
        "title=One More Time",
        "artist=Daft Punk",
    ]


def test_threads_are_only_added_when_asked():
    assert "-threads" not in build_audio_ffmpeg_args(plan())
    assert values(build_audio_ffmpeg_args(plan(threads=2)), "-threads") == [
        "2"
    ]
