from pathlib import Path

import pytest

from fakes.factories import make_facts
from fakes.fakes import FakeDownloader
from fakes.v03_fakes import make_audio_facts
from yt2wa.application.convert import ConvertUseCase
from yt2wa.application.dto import ConvertRequest, StrategyOutput
from yt2wa.application.strategies.base import ConversionStrategy
from yt2wa.domain.errors import (
    TranscodeError,
    UnsupportedSourceError,
    UsageError,
)
from yt2wa.domain.models import (
    DryRunPlan,
    MediaKind,
    Method,
    SourceMetadata,
    Target,
)
from yt2wa.domain.profile import DEFAULT_PROFILES
from yt2wa.infrastructure.local_workspace import LocalWorkspace

URL = "https://youtu.be/abcdefghijk"


class Stub(ConversionStrategy):
    """Writes a small file and remembers it ran."""

    def __init__(self, suffix, facts, fail=False):
        self.suffix, self.facts, self.fail = suffix, facts, fail
        self.ran = 0

    def run(self, ctx):
        self.ran += 1
        if self.fail:
            raise TranscodeError("boom")
        path = ctx.job_dir / f"result{self.suffix}"
        path.write_bytes(b"data")
        source = ctx.job_dir / f"source{self.suffix}"
        source.write_bytes(b"src")
        return StrategyOutput(
            path, Method.REMUX, self.facts, None, source=source
        )


class TitledDownloader(FakeDownloader):
    def __init__(self, title):
        super().__init__()
        self._title = title

    def probe(self, ref):
        return SourceMetadata(
            "abcdefghijk", self._title, 200.0, uploader="Daft Punk"
        )


def build(tmp_path, title="My Clip", fail=False):
    stubs = {
        (MediaKind.VIDEO, Target.CHAT): Stub(".mp4", make_facts()),
        (MediaKind.VIDEO, Target.STATUS): Stub(".mp4", make_facts()),
        (MediaKind.VIDEO, Target.ORIGINAL): Stub(".mkv", make_facts()),
        (MediaKind.AUDIO, Target.CHAT): Stub(".m4a", make_audio_facts(), fail),
        (MediaKind.AUDIO, Target.ORIGINAL): Stub(".webm", make_audio_facts()),
    }
    work = tmp_path / "work"
    usecase = ConvertUseCase(
        TitledDownloader(title),
        LocalWorkspace(work),
        stubs,
        DEFAULT_PROFILES,
    )
    return usecase, stubs, work


def request(tmp_path, media, target, **kw):
    return ConvertRequest(
        URL, target, 480, tmp_path / "out", media=media, **kw
    )


@pytest.mark.parametrize(
    ("media", "target"),
    [
        (MediaKind.VIDEO, Target.CHAT),
        (MediaKind.VIDEO, Target.STATUS),
        (MediaKind.VIDEO, Target.ORIGINAL),
        (MediaKind.AUDIO, Target.CHAT),
        (MediaKind.AUDIO, Target.ORIGINAL),
    ],
)
def test_each_request_runs_only_its_own_strategy(tmp_path, media, target):
    usecase, stubs, _ = build(tmp_path)
    usecase.execute(request(tmp_path, media, target))
    ran = {key: stub.ran for key, stub in stubs.items()}
    assert ran.pop((media, target)) == 1
    assert not any(ran.values())


def test_audio_cannot_be_a_status_and_nothing_is_downloaded(tmp_path):
    usecase, stubs, work = build(tmp_path)
    with pytest.raises(UsageError):
        usecase.execute(request(tmp_path, MediaKind.AUDIO, Target.STATUS))
    assert not any(stub.ran for stub in stubs.values())
    assert not work.exists()


def test_video_files_are_named_with_the_resolution(tmp_path):
    usecase, _, _ = build(tmp_path)
    result = usecase.execute(request(tmp_path, MediaKind.VIDEO, Target.CHAT))
    assert result.output.name == "My_Clip_480p.mp4"
    assert result.media is MediaKind.VIDEO


def test_audio_files_are_named_artist_and_title(tmp_path):
    usecase, _, _ = build(
        tmp_path, "Daft Punk - One More Time (Official Video)"
    )
    result = usecase.execute(request(tmp_path, MediaKind.AUDIO, Target.CHAT))
    assert result.output.name == "Daft_Punk_-_One_More_Time.m4a"
    assert result.media is MediaKind.AUDIO
    assert result.effective_resolution == 0
    assert result.warnings == ()


def test_kept_source_is_published_next_to_the_output(tmp_path):
    usecase, _, _ = build(tmp_path)
    result = usecase.execute(
        request(tmp_path, MediaKind.AUDIO, Target.CHAT, keep_source=True)
    )
    assert result.source_kept is not None
    assert result.source_kept.name.endswith("_source.m4a")


def test_audio_size_cap_comes_from_the_audio_profile(tmp_path):
    usecase, _, _ = build(tmp_path)
    audio = request(tmp_path, MediaKind.AUDIO, Target.CHAT)
    assert usecase._size_cap(audio, DEFAULT_PROFILES["chat"]) == 16 * 1024**2
    unlimited = request(tmp_path, MediaKind.AUDIO, Target.CHAT, max_size_mb=0)
    assert usecase._size_cap(unlimited, DEFAULT_PROFILES["chat"]) is None
    original = request(tmp_path, MediaKind.AUDIO, Target.ORIGINAL)
    assert usecase._size_cap(original, DEFAULT_PROFILES["chat"]) is None


def test_scratch_folders_are_removed_after_success_and_failure(tmp_path):
    usecase, _, work = build(tmp_path)
    usecase.execute(request(tmp_path, MediaKind.AUDIO, Target.CHAT))
    assert list(work.glob("job-*")) == []

    failing, _, work2 = build(tmp_path / "again", fail=True)
    with pytest.raises(TranscodeError):
        failing.execute(request(tmp_path, MediaKind.AUDIO, Target.CHAT))
    assert list(work2.glob("job-*")) == []


def test_unsupported_links_are_rejected(tmp_path):
    usecase, _, _ = build(tmp_path)
    bad = ConvertRequest("https://vimeo.com/1", Target.CHAT, 480, tmp_path)
    with pytest.raises(UnsupportedSourceError):
        usecase.execute(bad)


def test_dry_run_describes_audio_without_downloading(tmp_path):
    usecase, stubs, work = build(tmp_path)
    plan = usecase.execute(
        request(tmp_path, MediaKind.AUDIO, Target.CHAT, dry_run=True)
    )
    assert isinstance(plan, DryRunPlan)
    text = "\n".join(plan.lines)
    assert "Media:       audio" in text
    assert "128 kbit/s" in text
    assert not any(stub.ran for stub in stubs.values())
    assert not Path(work).exists()
