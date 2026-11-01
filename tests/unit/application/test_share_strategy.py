from pathlib import Path

import pytest

from fakes.factories import make_facts
from fakes.fakes import FakeDownloader, FakeProbe, FakeTranscoder
from yt2wa.application.dto import ConvertRequest, JobContext
from yt2wa.application.strategies.share import ShareStrategy
from yt2wa.domain.errors import SizeCapError
from yt2wa.domain.models import (
    Method,
    SourceKind,
    SourceMetadata,
    SourceRef,
    Target,
    ignore_progress,
)
from yt2wa.domain.profile import DEFAULT_CHAT

MB = 1024 * 1024


def run_strategy(tmp_path: Path, source_facts, sizes):
    downloader = FakeDownloader()
    transcoder = FakeTranscoder(sizes)
    strategy = ShareStrategy(
        downloader, FakeProbe(source_facts), transcoder
    )
    request = ConvertRequest(
        url="https://youtu.be/abcdefghijk",
        target=Target.CHAT,
        resolution=480,
        output_dir=tmp_path / "out",
    )
    ctx = JobContext(
        request=request,
        ref=SourceRef(request.url, SourceKind.VIDEO, "abcdefghijk"),
        metadata=SourceMetadata("abcdefghijk", "My Clip", 60.0),
        job_dir=tmp_path / "job",
        profile=DEFAULT_CHAT,
        size_cap_bytes=16 * MB,
        on_progress=ignore_progress,
    )
    return strategy.run(ctx), transcoder, downloader


def test_compliant_source_is_remuxed_without_re_encoding(tmp_path):
    source = make_facts(container="matroska,webm", faststart=None)
    output, transcoder, _ = run_strategy(tmp_path, source, [5 * MB])
    assert output.method is Method.REMUX
    assert len(transcoder.calls) == 1
    assert "copy" in transcoder.calls[0]


def test_non_compliant_source_is_transcoded(tmp_path):
    source = make_facts(vcodec="vp9", acodec="opus", faststart=None)
    output, transcoder, _ = run_strategy(tmp_path, source, [6 * MB])
    assert output.method is Method.TRANSCODE
    assert "libx264" in transcoder.calls[0]


def test_ladder_steps_down_until_the_file_fits(tmp_path):
    source = make_facts(vcodec="vp9", acodec="opus", faststart=None)
    output, transcoder, _ = run_strategy(
        tmp_path, source, [20 * MB, 10 * MB]
    )
    assert len(transcoder.calls) == 2
    assert "-crf" in transcoder.calls[0]
    assert "-b:v" in transcoder.calls[1]
    assert output.facts.size_bytes == 10 * MB


def test_oversize_compliant_source_falls_back_to_the_ladder(tmp_path):
    source = make_facts(size_bytes=30 * MB)
    output, transcoder, _ = run_strategy(
        tmp_path, source, [30 * MB, 9 * MB]
    )
    assert output.method is Method.TRANSCODE
    assert len(transcoder.calls) == 2


def test_fails_when_nothing_fits(tmp_path):
    source = make_facts(vcodec="vp9", acodec="opus", faststart=None)
    with pytest.raises(SizeCapError):
        run_strategy(tmp_path, source, [30 * MB] * 10)


def test_download_is_limited_to_the_requested_resolution(tmp_path):
    source = make_facts()
    _, _, downloader = run_strategy(tmp_path, source, [5 * MB])
    assert downloader.choices[0].sort[0] == "res:480"
