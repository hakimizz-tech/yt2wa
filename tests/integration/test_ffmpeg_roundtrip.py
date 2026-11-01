"""Run the real ffmpeg on a tiny video and check the result."""

import shutil
import subprocess

import pytest

from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.ffmpeg_args import FfmpegPlan, build_ffmpeg_args
from yt2wa.domain.models import Method, ignore_progress
from yt2wa.domain.profile import DEFAULT_CHAT
from yt2wa.infrastructure.ffmpeg_transcoder import FfmpegTranscoder
from yt2wa.infrastructure.ffprobe_probe import FfprobeMediaProbe

pytestmark = pytest.mark.ffmpeg


def has_encoders() -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return False
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return "libx264" in out and "mpeg4" in out


pytestmark = [
    pytest.mark.ffmpeg,
    pytest.mark.skipif(not has_encoders(), reason="ffmpeg not available"),
]


@pytest.fixture
def source(tmp_path):
    """A 1280x720, 60 fps MPEG-4 + MP3 clip that is NOT compliant."""
    path = tmp_path / "source.mkv"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=1280x720:rate=60",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "mpeg4", "-c:a", "libmp3lame", "-ac", "1",
            str(path),
        ],  # fmt: skip
        check=True,
    )
    return path


def test_transcode_output_passes_the_compliance_checker(source, tmp_path):
    probe = FfprobeMediaProbe()
    facts = probe.inspect(source)
    output = tmp_path / "out.mp4"
    plan = FfmpegPlan(
        source=source,
        output=output,
        method=Method.TRANSCODE,
        facts=facts,
        profile=DEFAULT_CHAT,
        short_cap=480,
    )
    FfmpegTranscoder().run(
        build_ffmpeg_args(plan), facts.duration_s, ignore_progress
    )

    result = probe.inspect(output)
    report = check_compliance(
        result, DEFAULT_CHAT, 16 * 1024 * 1024, short_cap=480,
        source_aspect=facts.aspect,
    )
    assert report.ok, [
        (r.name, r.expected, r.actual) for r in report.errors
    ]
    assert result.display_size == (854, 480)
    assert result.fps <= 30.05
    assert result.faststart is True
