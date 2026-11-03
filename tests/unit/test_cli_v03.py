import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fakes.v03_fakes import make_candidate
from yt2wa.application.dto import SearchOutcome
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import NotFoundError
from yt2wa.domain.models import (
    ProviderAttempt,
    ScoredCandidate,
    SearchProviderName,
    SearchResult,
    SourceMetadata,
)
from yt2wa.interface import cli
from yt2wa.interface.cli import build_parser, main
from yt2wa.interface.exit_codes import ExitCode, map_exception_to_exit_code
from yt2wa.interface.presenters import (
    ConsolePresenter,
    JsonPresenter,
    format_clock,
    format_count,
)

URL = "https://youtu.be/dQw4w9WgXcQ"
P = SearchProviderName


def parse(*argv):
    return build_parser().parse_args(argv)


def scored(video_id="aaaaaaaaaaa", score=0.86, **kw):
    cand = make_candidate(
        video_id, "Daft Punk - One More Time", "Daft Punk", **kw
    )
    return ScoredCandidate(
        cand, score, ("title matches 4/4 words",), "Daft Punk", "One More Time"
    )


def outcome(**kw):
    best, other = scored(), scored("bbbbbbbbbbb", 0.61)
    result = SearchResult(
        "daft punk",
        best,
        (other,),
        0.86,
        False,
        P.YTMUSICAPI,
        (ProviderAttempt(P.YTMUSICAPI, "ok"),),
    )
    return SearchOutcome(result, **kw)


# ---- parsing --------------------------------------------------------------


def test_audio_flags_parse():
    args = parse(
        "convert", URL, "-x", "--audio-format", "mp3", "--audio-bitrate", "96"
    )
    assert (
        args.audio and args.audio_format == "mp3" and args.audio_bitrate == 96
    )


def test_audio_command_maps_to_the_existing_audio_options():
    args = parse(
        "audio",
        URL,
        "--keep-original",
        "--format",
        "mp3",
        "--bitrate",
        "96",
        "--dry-run",
    )
    assert args.command == "audio"
    assert args.audio
    assert args.target == "original"
    assert args.audio_format == "mp3"
    assert args.audio_bitrate == 96
    assert args.dry_run


def test_audio_command_does_not_offer_video_only_options():
    with pytest.raises(SystemExit):
        parse("audio", URL, "--resolution", "480")
    with pytest.raises(SystemExit):
        parse("audio", URL, "--target", "status")


def test_search_flags_parse():
    args = parse(
        *["search", "daft", "punk", "--type", "music"],
        *["--provider", "ytmusicapi", "--limit", "3", "--detail"],
        *["--download", "--pick", "2", "-x"],
    )
    assert args.query == ["daft", "punk"]
    assert args.kind == "music" and args.provider == "ytmusicapi"
    assert args.limit == 3 and args.detail and args.download
    assert args.pick == 2 and args.audio


def test_search_is_a_known_command():
    assert cli.with_default_command(["search", "x"]) == ["search", "x"]


def test_bad_provider_and_bitrate_are_rejected_by_the_parser():
    with pytest.raises(SystemExit):
        parse("search", "x", "--provider", "spotify")
    with pytest.raises(SystemExit):
        parse("convert", URL, "-x", "--audio-bitrate", "100")


# ---- usage errors (no network, no container needed) -------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["convert", URL, "-x", "-t", "status"],
        ["convert", URL, "--audio-format", "mp3"],
        ["convert", URL, "--audio-bitrate", "96"],
        ["search", "x", "--pick", "2"],
        ["search", "x", "--min-confidence", "0.5"],
        ["search", "x", "-x"],
        ["search", "x", "-t", "chat"],
        ["search", "x", "-o", "somewhere"],
        ["search", "x", "--download", "-x", "-t", "status"],
        ["search", "x", "--download", "--audio-format", "mp3"],
    ],
)
def test_bad_combinations_exit_with_the_usage_code(argv, capsys):
    assert main(argv) == ExitCode.USAGE
    assert "[error]" in capsys.readouterr().err


def test_not_found_has_its_own_exit_code():
    assert ExitCode.NOT_FOUND == 9
    assert map_exception_to_exit_code(NotFoundError("x")) == ExitCode.NOT_FOUND


# ---- the search command with a fake container -------------------------------


class FakeSearch:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.requests = result, error, []

    def execute(self, request, on_progress=None):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def fake_container(monkeypatch):
    def install(search):
        container = SimpleNamespace(settings=Settings(), search=search)
        monkeypatch.setattr(cli, "build_container", lambda settings: container)
        return container

    monkeypatch.chdir(Path(__file__).parent)  # No .env here.
    return install


def test_search_prints_the_best_url_on_stdout(fake_container, capsys):
    search = FakeSearch(outcome())
    fake_container(search)
    assert main(["search", "daft", "punk", "--type", "music"]) == 0
    captured = capsys.readouterr()
    assert (
        captured.out.strip() == "https://www.youtube.com/watch?v=aaaaaaaaaaa"
    )
    assert "Best match (confidence 0.86) via ytmusicapi" in captured.err
    assert "Alternates:" in captured.err
    request = search.requests[0]
    assert request.query == "daft punk"
    assert request.kind.value == "music"
    assert request.limit == 5 and request.provider is None


def test_search_json_is_one_document_on_stdout(fake_container, capsys):
    fake_container(FakeSearch(outcome()))
    assert main(["search", "daft punk", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["result"]["provider"] == "ytmusicapi"
    assert data["result"]["best"]["candidate"]["video_id"] == "aaaaaaaaaaa"
    assert data["result"]["attempts"][0]["outcome"] == "ok"
    assert data["result"]["alternates"][0]["score"] == 0.61


def test_search_not_found_returns_exit_code_9(fake_container, capsys):
    fake_container(FakeSearch(error=NotFoundError("Nothing found.", "hint")))
    assert main(["search", "zzz"]) == 9
    assert "Nothing found." in capsys.readouterr().err


def test_search_options_reach_the_request(fake_container):
    search = FakeSearch(outcome())
    fake_container(search)
    main(["search", "x", "--provider", "ytsearch", "--limit", "9", "--detail"])
    request = search.requests[0]
    assert request.provider is P.YTSEARCH
    assert request.limit == 9 and request.detail


def test_provider_auto_means_no_explicit_provider(fake_container):
    search = FakeSearch(outcome())
    fake_container(search)
    main(["search", "x", "--provider", "auto"])
    assert search.requests[0].provider is None


def test_download_request_carries_the_audio_options(fake_container):
    search = FakeSearch(outcome())
    fake_container(search)
    main(
        [
            "search",
            "x",
            "--download",
            "-x",
            "--audio-bitrate",
            "96",
            "--pick",
            "2",
        ]
    )
    request = search.requests[0]
    assert request.pick == 2
    assert request.download is not None
    assert request.download.media.value == "audio"
    assert request.download.audio_bitrate_k == 96
    assert request.download.target.value == "chat"


# ---- presenters -------------------------------------------------------------


def test_console_presenter_shows_fallbacks_and_details():
    attempts = (
        ProviderAttempt(P.YTMUSICAPI, "error", "down"),
        ProviderAttempt(P.YTSEARCH, "ok"),
    )
    base = outcome()
    result = SearchResult(
        "q", base.result.best, (), 0.86, True, P.YTSEARCH, attempts
    )
    detail = SourceMetadata(
        "aaaaaaaaaaa", "t", 1.0, artist="Daft Punk", album="Discovery"
    )
    out, err = io.StringIO(), io.StringIO()
    ConsolePresenter(out=out, err=err).search(
        SearchOutcome(result, detail=detail, notes=("careful",))
    )
    text = err.getvalue()
    assert "ytmusicapi (error: down), ytsearch (ok)" in text
    assert "album: Discovery" in text
    assert "equally well" in text
    assert "careful" in text
    assert out.getvalue().strip().endswith("aaaaaaaaaaa")


def test_quiet_search_prints_only_the_url():
    out, err = io.StringIO(), io.StringIO()
    ConsolePresenter(quiet=True, out=out, err=err).search(outcome())
    assert err.getvalue() == ""
    assert out.getvalue().strip().endswith("aaaaaaaaaaa")


def test_json_presenter_ignores_notes():
    out = io.StringIO()
    presenter = JsonPresenter(out=out)
    presenter.note("hello")
    assert out.getvalue() == ""


@pytest.mark.parametrize(
    ("seconds", "text"), [(0, "0:00"), (222, "3:42"), (3723, "1:02:03")]
)
def test_format_clock(seconds, text):
    assert format_clock(seconds) == text


@pytest.mark.parametrize(
    ("count", "text"),
    [(None, "? views"), (950, "950 views"), (1500, "1.5K views"),
     (612_300_000, "612.3M views"), (2_000_000_000, "2.0B views")],
)  # fmt: skip
def test_format_count(count, text):
    assert format_count(count) == text
