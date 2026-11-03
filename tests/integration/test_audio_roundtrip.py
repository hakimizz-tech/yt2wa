"""Run the real ffmpeg on a generated tone and check the audio output."""

import json
import shutil
import subprocess

import pytest

from yt2wa.domain.audio_compliance import (
    check_audio_compliance,
    decide_audio_path,
)
from yt2wa.domain.audio_ffmpeg_args import AudioPlan, build_audio_ffmpeg_args
from yt2wa.domain.audio_profile import DEFAULT_AUDIO
from yt2wa.domain.models import AudioFormat, Method, ignore_progress
from yt2wa.infrastructure.ffmpeg_transcoder import FfmpegTranscoder
from yt2wa.infrastructure.ffprobe_probe import FfprobeMediaProbe

MB = 1024 * 1024


def has_encoders() -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return False
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return " aac " in out and "libmp3lame" in out


pytestmark = [
    pytest.mark.ffmpeg,
    pytest.mark.skipif(not has_encoders(), reason="ffmpeg not available"),
]


def make_tone(path, *codec_args):
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3",
            *codec_args,
            str(path),
        ],  # fmt: skip
        check=True,
    )


def convert(source, output, method, fmt, tags=None, bitrate=128):
    probe = FfprobeMediaProbe()
    facts = probe.inspect(source)
    plan = AudioPlan(
        source=source,
        output=output,
        method=method,
        facts=facts,
        profile=DEFAULT_AUDIO,
        audio_format=fmt,
        bitrate_k=bitrate,
        tags=tags or {},
    )
    FfmpegTranscoder().run(
        build_audio_ffmpeg_args(plan), facts.duration_s, ignore_progress
    )
    return probe.inspect(output)


def format_tags(path):
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)["format"].get("tags", {})


def test_aac_without_faststart_is_remuxed_losslessly(tmp_path):
    source = tmp_path / "source.m4a"
    make_tone(source, "-c:a", "aac", "-ac", "2", "-ar", "44100")
    facts = FfprobeMediaProbe().inspect(source)
    report = check_audio_compliance(facts, DEFAULT_AUDIO, 16 * MB)
    assert decide_audio_path(report).method is Method.REMUX

    result = convert(
        source, tmp_path / "out.m4a", Method.REMUX, AudioFormat.M4A,
        {"title": "Tone", "artist": "Tester"},
    )  # fmt: skip
    after = check_audio_compliance(result, DEFAULT_AUDIO, 16 * MB)
    assert after.ok, [(r.name, r.expected, r.actual) for r in after.errors]
    assert result.faststart is True
    assert result.acodec == "aac"
    tags = format_tags(tmp_path / "out.m4a")
    assert tags.get("title") == "Tone"
    assert tags.get("artist") == "Tester"


def test_mp3_source_is_transcoded_to_a_compliant_m4a(tmp_path):
    source = tmp_path / "source.mp3"
    make_tone(source, "-c:a", "libmp3lame", "-ac", "1", "-ar", "22050")
    facts = FfprobeMediaProbe().inspect(source)
    report = check_audio_compliance(facts, DEFAULT_AUDIO, 16 * MB)
    assert decide_audio_path(report).method is Method.TRANSCODE

    result = convert(
        source, tmp_path / "out.m4a", Method.TRANSCODE, AudioFormat.M4A
    )
    after = check_audio_compliance(result, DEFAULT_AUDIO, 16 * MB)
    assert after.ok, [(r.name, r.expected, r.actual) for r in after.errors]
    assert result.sample_rate == 48000
    assert result.channels == 1
    assert result.vcodec is None


def test_m4a_is_transcoded_to_a_compliant_mp3(tmp_path):
    source = tmp_path / "source.m4a"
    make_tone(source, "-c:a", "aac", "-ac", "2", "-ar", "44100")
    result = convert(
        source, tmp_path / "out.mp3", Method.TRANSCODE, AudioFormat.MP3,
        bitrate=96,
    )  # fmt: skip
    after = check_audio_compliance(
        result, DEFAULT_AUDIO, 16 * MB, AudioFormat.MP3, 96
    )
    assert after.ok, [(r.name, r.expected, r.actual) for r in after.errors]
    assert result.acodec == "mp3"
