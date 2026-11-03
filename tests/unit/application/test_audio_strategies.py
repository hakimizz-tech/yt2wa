from pathlib import Path

import pytest

from fakes.fakes import FakeDownloader, FakeTranscoder
from fakes.v03_fakes import FakeAudioProbe, make_audio_facts
from yt2wa.application.dto import ConvertRequest, JobContext
from yt2wa.application.strategies.audio_original import AudioOriginalStrategy
from yt2wa.application.strategies.audio_share import AudioShareStrategy
from yt2wa.domain.audio_profile import DEFAULT_AUDIO
from yt2wa.domain.errors import NonCompliantOutputError, SizeCapError
from yt2wa.domain.models import (
    AudioFormat,
    MediaKind,
    Method,
    SourceKind,
    SourceMetadata,
    SourceRef,
    Target,
    ignore_progress,
)
from yt2wa.domain.profile import DEFAULT_CHAT

MB = 1024 * 1024
TITLE = "Daft Punk - One More Time (Official Video)"


def context(tmp_path, target=Target.CHAT, fmt=AudioFormat.M4A, duration=200.0):
    request = ConvertRequest(
        url="https://youtu.be/abcdefghijk",
        target=target,
        resolution=480,
        output_dir=tmp_path / "out",
        media=MediaKind.AUDIO,
        audio_format=fmt,
    )
    return JobContext(
        request=request,
        ref=SourceRef(request.url, SourceKind.VIDEO, "abcdefghijk"),
        metadata=SourceMetadata("abcdefghijk", TITLE, duration, "Daft Punk"),
        job_dir=tmp_path / "job",
        profile=DEFAULT_CHAT,
        size_cap_bytes=16 * MB if target.is_shareable else None,
        on_progress=ignore_progress,
        audio_profile=DEFAULT_AUDIO,
    )


def share(tmp_path, source, sizes, **ctx):
    downloader = FakeDownloader()
    transcoder = FakeTranscoder(sizes)
    strategy = AudioShareStrategy(
        downloader, FakeAudioProbe(source), transcoder
    )
    output = strategy.run(context(tmp_path, **ctx))
    return output, transcoder, downloader


def test_compliant_aac_without_faststart_is_remuxed(tmp_path):
    source = make_audio_facts(faststart=False)
    output, transcoder, _ = share(tmp_path, source, [3 * MB])
    assert output.method is Method.REMUX
    assert len(transcoder.calls) == 1
    assert "copy" in transcoder.calls[0]


def test_opus_source_is_transcoded_to_aac_with_tags(tmp_path):
    source = make_audio_facts(
        container="matroska,webm", acodec="opus", aprofile=None,
        faststart=None, sample_rate=48000,
    )  # fmt: skip
    output, transcoder, _ = share(tmp_path, source, [3 * MB])
    assert output.method is Method.TRANSCODE
    args = transcoder.calls[0]
    assert "aac" in args
    assert "title=One More Time" in args
    assert "artist=Daft Punk" in args


def test_ladder_steps_down_until_the_file_fits(tmp_path):
    source = make_audio_facts(acodec="opus", aprofile=None, container="webm")
    output, transcoder, _ = share(tmp_path, source, [20 * MB, 5 * MB])
    assert len(transcoder.calls) == 2
    assert "128k" in transcoder.calls[0]
    assert "96k" in transcoder.calls[1]
    assert output.facts.size_bytes == 5 * MB


def test_audio_that_is_too_long_fails_before_any_encoding(tmp_path):
    source = make_audio_facts(
        acodec="opus", aprofile=None, container="webm", duration_s=7200.0
    )
    with pytest.raises(SizeCapError):
        share(tmp_path, source, [], duration=7200.0)


def test_mp3_format_uses_lame(tmp_path):
    source = make_audio_facts(acodec="opus", aprofile=None, container="webm")
    # The fake probe reports m4a-style facts for candidates, so only the
    # command line is checked here.
    transcoder = FakeTranscoder([3 * MB])
    strategy = AudioShareStrategy(
        FakeDownloader(), FakeAudioProbe(source), transcoder
    )
    try:
        strategy.run(context(tmp_path, fmt=AudioFormat.MP3))
    except NonCompliantOutputError:
        pass  # Fake facts are m4a, which is not valid for mp3.
    assert "libmp3lame" in transcoder.calls[0]


def test_download_asks_for_aac_first(tmp_path):
    source = make_audio_facts()
    _, _, downloader = share(tmp_path, source, [3 * MB])
    assert downloader.choices[0].sort[0] == "acodec:aac"


def test_source_without_audio_is_rejected(tmp_path):
    source = make_audio_facts(acodec=None, aprofile=None)
    with pytest.raises(NonCompliantOutputError):
        share(tmp_path, source, [])


def test_original_audio_is_downloaded_as_is(tmp_path):
    strategy = AudioOriginalStrategy(
        FakeDownloader(), FakeAudioProbe(make_audio_facts())
    )
    output = strategy.run(context(tmp_path, target=Target.ORIGINAL))
    assert output.method is Method.DOWNLOAD
    assert output.warnings == ()
    assert Path(output.path).name == "source.mkv"


def test_original_audio_warns_when_not_shareable(tmp_path):
    source = make_audio_facts(acodec="opus", aprofile=None, container="webm")
    strategy = AudioOriginalStrategy(FakeDownloader(), FakeAudioProbe(source))
    output = strategy.run(context(tmp_path, target=Target.ORIGINAL))
    assert len(output.warnings) == 1
    assert "opus" in output.warnings[0]
