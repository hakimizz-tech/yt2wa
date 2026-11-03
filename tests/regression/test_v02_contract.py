"""Guards that v0.3 did not break anything v0.2 promised.

These tests describe v0.2 behaviour. They pass on v0.2 and must keep
passing on every later version.
"""

import inspect
import json
from pathlib import Path

from fakes.factories import make_facts
from yt2wa.application.convert import ConvertUseCase
from yt2wa.application.dto import ConvertRequest, JobContext, VerifyRequest
from yt2wa.application.strategies.original import OriginalStrategy
from yt2wa.application.strategies.share import ShareStrategy
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.compliance import check_compliance
from yt2wa.domain.ffmpeg_args import FfmpegPlan, build_ffmpeg_args
from yt2wa.domain.models import (
    BEST_RESOLUTION,
    RESOLUTION_RUNGS,
    ConversionResult,
    LadderStep,
    Method,
    Target,
)
from yt2wa.domain.profile import DEFAULT_CHAT, DEFAULT_PROFILES
from yt2wa.interface.cli import build_parser, with_default_command
from yt2wa.interface.exit_codes import ExitCode
from yt2wa.interface.presenters import to_jsonable

URL = "https://youtu.be/dQw4w9WgXcQ"


def names(function):
    return list(inspect.signature(function).parameters)


# ---- public API shapes ------------------------------------------------------


def test_request_and_strategy_signatures_are_unchanged():
    assert names(ShareStrategy.__init__)[:6] == [
        "self", "downloader", "probe", "transcoder", "ffmpeg_bin", "threads",
    ]  # fmt: skip
    assert names(OriginalStrategy.__init__)[:3] == [
        "self", "downloader", "probe",
    ]  # fmt: skip
    assert names(check_compliance)[:5] == [
        "facts", "profile", "size_cap_bytes", "short_cap", "source_aspect",
    ]  # fmt: skip
    assert names(ConvertUseCase.__init__)[:5] == [
        "self", "downloader", "workspace", "strategies", "profiles",
    ]  # fmt: skip


def test_v02_style_requests_still_work_and_default_to_video(tmp_path):
    request = ConvertRequest(URL, Target.CHAT, 480, tmp_path)
    assert request.media.value == "video"
    assert request.max_size_mb is None and not request.dry_run
    assert JobContext.__dataclass_fields__["audio_profile"].default is None


def test_convert_use_case_still_accepts_target_keyed_strategies(tmp_path):
    from fakes.fakes import FakeDownloader
    from yt2wa.infrastructure.local_workspace import LocalWorkspace

    class Marker:
        pass

    legacy = {Target.CHAT: Marker()}
    usecase = ConvertUseCase(
        FakeDownloader(), LocalWorkspace(tmp_path), legacy, DEFAULT_PROFILES
    )
    keys = list(usecase._strategies)
    assert keys[0][1] is Target.CHAT and keys[0][0].value == "video"


def test_v02_exit_codes_keep_their_numbers():
    assert {c.name: int(c) for c in ExitCode if c.name != "NOT_FOUND"} == {
        "OK": 0, "GENERAL": 1, "USAGE": 2, "UNSUPPORTED": 3,
        "UNAVAILABLE": 4, "NETWORK": 5, "DEPENDENCY": 6, "TRANSCODE": 7,
        "CONSTRAINT": 8, "INTERRUPTED": 130,
    }  # fmt: skip


def test_resolution_values_are_unchanged():
    assert RESOLUTION_RUNGS == (144, 240, 360, 480, 720, 1080)
    assert BEST_RESOLUTION == 0


def test_default_settings_are_unchanged():
    defaults = Settings()
    assert defaults.default_target is Target.CHAT
    assert defaults.default_resolution == 480
    assert defaults.net_retries == 3
    assert DEFAULT_CHAT.size_cap_mb == 16
    assert DEFAULT_CHAT.crf == 23


# ---- command line -----------------------------------------------------------


def test_v02_command_line_still_parses():
    parser = build_parser()
    args = parser.parse_args(
        ["convert", URL, "-t", "status", "-r", "720", "--max-size", "8",
         "--report", "--keep-source", "--dry-run", "-o", "out", "--json", "-q"]
    )  # fmt: skip
    assert args.target == "status" and args.resolution == 720
    assert args.max_size == 8 and args.report and args.keep_source
    assert args.dry_run and args.json and args.quiet
    assert (
        parser.parse_args(["convert", URL, "--keep-original"]).target
        == "original"
    )
    assert (
        parser.parse_args(["verify", "f.mp4", "-t", "status"]).target
        == "status"
    )
    assert parser.parse_args(["clean", "--hours", "2"]).hours == 2.0
    assert parser.parse_args(["doctor"]).command == "doctor"


def test_a_bare_link_still_means_convert():
    assert with_default_command([URL, "-r", "720"])[0] == "convert"


def test_video_defaults_are_not_audio():
    args = build_parser().parse_args(["convert", URL])
    assert not args.audio and args.audio_format is None


# ---- golden ffmpeg command lines (video path must never drift) --------------


def plan(method=Method.TRANSCODE, step=None, **facts):
    return FfmpegPlan(
        source=Path("in.mkv"),
        output=Path("out.mp4"),
        method=method,
        facts=make_facts(**facts),
        profile=DEFAULT_CHAT,
        short_cap=480,
        step=step,
    )


BASE = [
    "ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
    "-progress", "pipe:1", "-nostats", "-i", "in.mkv",
    "-map", "0:v:0", "-map", "0:a:0?",
]  # fmt: skip


def test_golden_transcode_command():
    assert build_ffmpeg_args(plan(width=1280, height=720)) == BASE + [
        "-vf", "scale=854:480:flags=lanczos",
        "-c:v", "libx264", "-preset", "medium", "-profile:v", "high",
        "-level:v", "3.0", "-pix_fmt", "yuv420p",
        "-crf", "23", "-maxrate", "1400k", "-bufsize", "2800k",
        "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "128k",
        "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "out.mp4",
    ]  # fmt: skip


def test_golden_bitrate_step_command():
    step = LadderStep("bitrate", 480, 900)
    assert build_ffmpeg_args(plan(step=step)) == BASE + [
        "-c:v", "libx264", "-preset", "medium", "-profile:v", "high",
        "-level:v", "3.0", "-pix_fmt", "yuv420p",
        "-b:v", "900k", "-maxrate", "900k", "-bufsize", "1800k",
        "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "128k",
        "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "out.mp4",
    ]  # fmt: skip


def test_golden_remux_command():
    assert build_ffmpeg_args(plan(method=Method.REMUX)) == BASE + [
        "-c", "copy", "-movflags", "+faststart", "out.mp4",
    ]  # fmt: skip


# ---- results keep their JSON shape ------------------------------------------


def test_video_result_json_keeps_its_v02_keys():
    result = ConversionResult(
        output=Path("out/x.mp4"),
        target=Target.CHAT,
        method=Method.REMUX,
        title="x",
        requested_resolution=480,
        effective_resolution=480,
        size_bytes=1,
        report=None,
    )
    data = json.loads(json.dumps(to_jsonable(result)))
    assert {
        "output", "target", "method", "title", "requested_resolution",
        "effective_resolution", "size_bytes", "report", "warnings",
        "source_kept",
    } <= set(data)  # fmt: skip
    assert data["target"] == "chat" and data["method"] == "remux"


def test_verify_request_is_unchanged():
    assert names(VerifyRequest)[:2] == ["path", "target"]
