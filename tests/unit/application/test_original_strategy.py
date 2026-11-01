from fakes.factories import make_facts
from fakes.fakes import FakeDownloader, FakeProbe
from yt2wa.application.dto import ConvertRequest, JobContext
from yt2wa.application.strategies.original import OriginalStrategy
from yt2wa.domain.models import (
    Method,
    SourceKind,
    SourceMetadata,
    SourceRef,
    Target,
    ignore_progress,
)
from yt2wa.domain.profile import DEFAULT_CHAT


def run(tmp_path, facts):
    strategy = OriginalStrategy(FakeDownloader(), FakeProbe(facts))
    request = ConvertRequest(
        url="https://youtu.be/abcdefghijk",
        target=Target.ORIGINAL,
        resolution=480,
        output_dir=tmp_path,
    )
    ctx = JobContext(
        request=request,
        ref=SourceRef(request.url, SourceKind.VIDEO, "abcdefghijk"),
        metadata=SourceMetadata("abcdefghijk", "My Clip", 60.0),
        job_dir=tmp_path / "job",
        profile=DEFAULT_CHAT,
        size_cap_bytes=None,
        on_progress=ignore_progress,
    )
    return strategy.run(ctx)


def test_original_is_never_converted(tmp_path):
    output = run(tmp_path, make_facts())
    assert output.method is Method.DOWNLOAD
    assert output.path.name == "source.mkv"
    assert output.warnings == ()


def test_unshareable_original_gets_a_warning(tmp_path):
    output = run(tmp_path, make_facts(vcodec="vp9", acodec="opus"))
    assert len(output.warnings) == 1
    assert "--target chat" in output.warnings[0]
